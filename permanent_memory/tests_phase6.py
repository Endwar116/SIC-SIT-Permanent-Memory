#!/usr/bin/env python3
"""VS-9 Phase 6 測試：鏈式 audit＋F7 根治（R-2 寫入順序全流程）
預測（執行前落盤）：
  AU1 append×3 → verify ok, entries=3
  AU2 竄改中段 details → verify fail at 1
  AU3 外錨後砍尾 → verify_against_head fail（裸 verify 仍 ok=盲區對照）
  AU4 store.write 走鏈式 audit → verify ok
  AU5 F7 根治：假 ruling_audit_id 終態單元 → REJECTED(R-2-verify)；
      真流程（裁定先入鏈取 id→單元後寫）→ WRITE_NEW（R-2 順序全流程首次跑通）
"""
import copy, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from audit_chain import ChainedAudit
from store import MemoryStore
from tests_phase1_base import BASE

TD = Path(__file__).parent / "data_test_p6"
if TD.exists():
    _old = TD.parent / "data_test_p6_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TD), str(_old / f"run_{len(list(_old.iterdir()))}"))
results = []
def check(name, expect, got):
    ok = expect == got; results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")

A = ChainedAudit(TD / "solo" / "audit.jsonl")
for i in range(3): A.append("test_event", "system", {"i": i})
v = A.verify(); check("AU1", (True, 3), (v["ok"], v["entries"]))
# AU2 竄改
lines = (TD / "solo" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
mid = json.loads(lines[1]); mid["details"]["i"] = 999
lines[1] = json.dumps(mid, ensure_ascii=False)
tampered = TD / "solo" / "audit_tampered.jsonl"
tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
T = ChainedAudit(tampered); v2 = T.verify()
check("AU2", (False, 1), (v2["ok"], v2["at"]))
# AU3 外錨+砍尾
A.checkpoint_head()
orig = (TD / "solo" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
(TD / "solo" / "audit.jsonl").write_text("\n".join(orig[:-1]) + "\n", encoding="utf-8")
naked = A.verify(); anchored = A.verify_against_head()
check("AU3", (True, False), (naked["ok"], anchored["ok"]))
# AU4 store 整合
S = MemoryStore(TD / "store")
u = copy.deepcopy(BASE); u["id"] = "mu-p6000001"
S.write(u)
check("AU4", True, S.audit.verify()["ok"])
# AU5 F7 根治
fake = copy.deepcopy(BASE); fake["id"] = "mu-p6000fak"
fake["dna"]["primitives"]["task"] = {"id": "VS-9", "title": "t", "deliverable": "d", "status": "completed", "created_round": 1}
fake["audit_trail"] = [{"audit_id": "AUD-FAKE", "audit_type": "task_terminal_ruling", "actor": "system",
                        "timestamp": "t", "details": {"ruling_audit_id": "AUD-FAKE"}}]
r_fake = S.write(fake)
fake_rule = r_fake["validator"]["errors"][0]["rule"] if r_fake["action"] == "REJECTED" else "?"
# 真流程：裁定先入鏈
ruling = S.audit.append("task_terminal_ruling", "human", {"subject": "測試任務結案", "ruled_by": "human-simulated"})
real = copy.deepcopy(fake); real["id"] = "mu-p6000rea"
real["dna"]["primitives"]["entity"][0]["value"] = "真流程單元（避開與假件相似收編）：R-2 寫入順序完整演練，裁定先入鏈後寫記憶"
real["audit_trail"] = [{"audit_id": ruling["audit_id"], "audit_type": "task_terminal_ruling", "actor": "human",
                        "timestamp": ruling["timestamp"], "details": {"ruling_audit_id": ruling["audit_id"]}}]
r_real = S.write(real)
check("AU5", ("REJECTED", "R-2-verify", "WRITE_NEW"), (r_fake["action"], fake_rule, r_real["action"]))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
