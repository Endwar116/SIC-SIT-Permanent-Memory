#!/usr/bin/env python3
"""VS-9 Store 層測試（T10-lite 跨對話恢復＋Storage Contract 實測）
預測（執行前落盤）：
  S1 合法新單元 write            → WRITE_NEW＋檔案存在＋unit_written audit
  S2 非法單元（缺task key）       → REJECTED＋units/ 無新檔＋write_rejected audit
  S3 一模一樣再寫一次            → MERGE（版本不動、無新檔、權重+0.05）
  S4 同任務演化版                → VERSION_UPDATE（版本2、history=1）
  S5 對 immutable 演化寫入       → BAPReject＋bap_reject audit
  S6 目錄無 .tmp 殘留（M-2 乾淨）→ 0 個
  S7 新 store 實例重載（T10-lite）→ 單元數一致＋內容 roundtrip 相等
  S8 query 三軸（entity/task/time）→ 各命中正確
"""
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from store import BAPReject, MemoryStore
from tests_phase1_base import BASE

ROOT = Path(__file__).parent / "data_test_store"
if ROOT.exists():
    _old = ROOT.parent / "data_test_store_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(ROOT), str(_old / f"run_{len(list(_old.iterdir()))}"))

results = []


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


def audits(s):
    return [json.loads(l)["audit_type"] for l in open(s.audit_path, encoding="utf-8")] if s.audit_path.exists() else []


TASK = {"id": "VS-9", "title": "橋接", "deliverable": "store層", "status": "in_progress", "created_round": 1}


def mk(uid, state_val="store test", task=TASK, chain=None):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["dna"]["primitives"]["state"][0]["value"] = state_val
    u["dna"]["primitives"]["task"] = task
    u["dna"]["causal_chain"] = chain or ["t1", "p1", "o1"]
    return u


S = MemoryStore(ROOT)
# S1
r1 = S.write(mk("mu-s0000001"))
check("S1", ("WRITE_NEW", True, True),
      (r1["action"], (ROOT / "units" / "mu-s0000001.json").exists(), "unit_written" in audits(S)))
# S2
bad = mk("mu-s0000bad"); del bad["dna"]["primitives"]["task"]
r2 = S.write(bad)
check("S2", ("REJECTED", False, True),
      (r2["action"], (ROOT / "units" / "mu-s0000bad.json").exists(), "write_rejected" in audits(S)))
# S3
r3 = S.write(mk("mu-s0000002"))
u_after = S.get("mu-s0000001")
check("S3", ("MERGE", 1, 1, 0.15),
      (r3["action"], len(list((ROOT / "units").glob("*.json"))), u_after["version"]["current_number"],
       round(u_after["weight"]["dynamic"]["value"], 2)))
# S4
r4 = S.write(mk("mu-s0000003", state_val="store test 演化：加了加密層", chain=["t1", "p1", "o2"]))
u4 = S.get("mu-s0000001")
check("S4", ("VERSION_UPDATE", 2, 1), (r4["action"], u4["version"]["current_number"], len(u4["version"]["history"])))
# S5
u4["storage"]["retention_class"] = "immutable"
S._persist(u4)
try:
    S.write(mk("mu-s0000004", state_val="不該進去", chain=["t1", "p1", "o3"]))
    check("S5", "BAPReject", "no-raise")
except BAPReject:
    check("S5", "BAPReject", "BAPReject" if "bap_reject" in audits(S) else "raise-no-audit")
# S6
check("S6", 0, len(list((ROOT / "units").glob("*.tmp"))))
# S7（T10-lite：新實例=新對話）
S2_ = MemoryStore(ROOT)
check("S7", (1, True), (len(S2_.load_all()), S2_.get("mu-s0000001") == u4))
# S8
q_ent = S2_.query(entity_id="e1")
q_task = S2_.query(task_id="VS-9")
q_none = S2_.query(task_id="VS-4")
check("S8", (1, 1, 0), (len(q_ent), len(q_task), len(q_none)))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
