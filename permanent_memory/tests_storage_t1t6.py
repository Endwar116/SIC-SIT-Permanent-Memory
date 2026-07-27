#!/usr/bin/env python3
"""VS-9：T1/T6 儲存級驗收（設計審查 §6-3：從「邏輯通過」升「儲存通過」的關卡）
預測（執行前落盤）：
  TS1 T1儲存級：v1→v2→v3 全走 store.write（dedup VU 路徑）→ 關店重開新實例
      → version=3、history=2、history[0] 核心=最初版（血統落盤後仍完整）
  TS2 一模一樣再寫 → MERGE → 重載 version 仍 3（merge 不升版在儲存層成立）
  TS3 T6儲存級：三個過期 expected_version 的併發升版 → 分支1/2落盤、第3個觸發
      overflow → 重載後 locked=True、branches=3（併發狀態存活重啟）
  TS4 human 仲裁勝方 → 重載後 version=4、branches=[]、locked=False
  TS5 store 的鏈式 audit 全程 verify ok 且含 branch_created×3+branch_overflow
"""
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mutation as mu
from store import MemoryStore
from tests_phase1_base import BASE

TD = Path(__file__).parent / "data_test_t1t6"
if TD.exists():
    _old = TD.parent / "data_test_t1t6_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TD), str(_old / f"run_{len(list(_old.iterdir()))}"))

results = []


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


TASK = {"id": "VS-9", "title": "T1T6", "deliverable": "儲存級", "status": "in_progress", "created_round": 1}


def mk(uid, state_val):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["dna"]["primitives"]["task"] = TASK
    u["dna"]["primitives"]["state"][0]["value"] = state_val
    u["dna"]["causal_chain"] = ["t", "p", "o"]
    return u


S = MemoryStore(TD)
S.write(mk("mu-t1s00001", "第一版：初始狀態"))
S.write(mk("mu-t1s00002", "第一版：初始狀態，推進到第二階段了"))
S.write(mk("mu-t1s00003", "第一版：初始狀態，推進到第二階段了，現在完成第三階段"))
# TS1：關店重開
S2 = MemoryStore(TD)
u = S2.get("mu-t1s00001")
check("TS1", (3, 2, "第一版：初始狀態"),
      (u["version"]["current_number"], len(u["version"]["history"]),
       u["version"]["history"][0]["core_snapshot"]["primitives"]["state"][0]["value"]))
# TS2
S2.write(copy.deepcopy(u) | {"id": "mu-t1s0dup0"})
check("TS2", 3, MemoryStore(TD).get("mu-t1s00001")["version"]["current_number"])

# TS3：三個過期併發（instance B/C/D 都拿著 expected=3 的舊讀）
cur = MemoryStore(TD).get("mu-t1s00001")
inst = MemoryStore(TD)
audit_fn = lambda t, a, d: inst.audit.append(t, a, d)
for who, val in [("instB", "分支B主張"), ("instC", "分支C主張"), ("instD", "分支D主張")]:
    fresh = inst.get("mu-t1s00001")
    fresh["version"]["current_number"] = 4  # 模擬主線已被推進到 v4（讀者手上 expected 仍=3 過期）
    inst._persist(fresh)
    r = mu.write_with_lock(inst.get("mu-t1s00001"), 3, "version_update", who, audit_fn,
                           new_primitives={"state": [{"dimension": "context", "value": val}]},
                           change_summary=f"{who} 併發")
    inst._persist(r["unit"])
re = MemoryStore(TD).get("mu-t1s00001")
check("TS3", (True, 3), (re["version"].get("locked", False), len(re["version"].get("branches", []))))
# TS4：human 仲裁
resolved = mu.resolve_branches(re, "branch-2", actor="human", audit_fn=audit_fn)
inst._persist(resolved)
re2 = MemoryStore(TD).get("mu-t1s00001")
check("TS4", (5, 0, False),
      (re2["version"]["current_number"], len(re2["version"].get("branches", [])), re2["version"].get("locked", True)))
# TS5
v = inst.audit.verify()
types = [json.loads(l)["audit_type"] for l in open(inst.audit_path, encoding="utf-8")]
check("TS5", (True, 3, True), (v["ok"], types.count("branch_created"), "branch_overflow" in types))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
