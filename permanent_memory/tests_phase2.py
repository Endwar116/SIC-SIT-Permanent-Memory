#!/usr/bin/env python3
"""VS-9 Phase 2 測試（T1 場景子集：版本演化 history 完整、merge 不升版）
預測（執行前落盤）：
  M1 merge 調權重             → version 不變(1)、combined 更新、core 不動
  M2 version_update 改 state  → number 1→2、history[0] 含 v1 core_snapshot、summary 在檔
  M3 連續兩次升版             → number=3、history 長度 2、血統可回溯到 v1
  M4 immutable 升版           → MutationLawError
  M5 task→completed 無裁定id  → MutationLawError（R-2）
  M6 task→completed 有裁定id  → 升版＋task_terminal_ruling 入 audit＋pm_validate=PASS
  M7 無 change_summary        → MutationLawError
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mutation as mu
import pm_validate
from tests_phase1_base import BASE

results = []


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# M1
u1 = mu.merge(BASE, weight_dynamic_value=0.5)
check("M1", (1, 0.5, True), (u1["version"]["current_number"], u1["weight"]["combined"],
                             u1["dna"] == BASE["dna"]))
# M2
u2 = mu.version_update(BASE, new_primitives={"state": [{"dimension": "context", "value": "phase2"}]},
                       change_summary="state 更新測試")
check("M2", (2, 1, "phase1 test", "state 更新測試"),
      (u2["version"]["current_number"], len(u2["version"]["history"]),
       u2["version"]["history"][0]["core_snapshot"]["primitives"]["state"][0]["value"],
       u2["version"]["history"][0]["change_summary"]))
# M3
u3 = mu.version_update(u2, new_primitives={"state": [{"dimension": "context", "value": "phase2-again"}]},
                       change_summary="再升一版")
check("M3", (3, 2, "phase1 test"),
      (u3["version"]["current_number"], len(u3["version"]["history"]),
       u3["version"]["history"][0]["core_snapshot"]["primitives"]["state"][0]["value"]))
# M4
u = copy.deepcopy(BASE); u["storage"]["retention_class"] = "immutable"
try:
    mu.version_update(u, change_summary="不該成功")
    check("M4", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("M4", "MutationLawError", "MutationLawError")
# M5
task = {"id": "VS-9", "title": "t", "deliverable": "d", "status": "completed", "created_round": 1}
try:
    mu.version_update(BASE, new_primitives={"task": task}, change_summary="終態無裁定")
    check("M5", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("M5", "MutationLawError", "MutationLawError")
# M6
u6 = mu.version_update(BASE, new_primitives={"task": task}, change_summary="終態含裁定",
                       ruling_audit_id="AUD-TEST-001", actor="human")
v6 = pm_validate.validate_unit(u6)
check("M6", (2, "task_terminal_ruling", "PASS"),
      (u6["version"]["current_number"],
       u6["audit_trail"][-1]["audit_type"], v6["status"]))
# M7
try:
    mu.version_update(BASE, new_primitives={"state": [{"dimension": "x", "value": "y"}]}, change_summary="")
    check("M7", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("M7", "MutationLawError", "MutationLawError")

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
