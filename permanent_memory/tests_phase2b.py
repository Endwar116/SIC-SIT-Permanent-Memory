#!/usr/bin/env python3
"""VS-9 Phase 2b 測試：F6 修＋樂觀鎖＋Branch Model（T6 場景子集）
預測（執行前落盤）：
  N1 version_update 核心無變化           → MutationLawError(no-op)
  L1 expected==current 的 vu             → committed, version 2
  L2 過期 expected 的 merge              → committed_after_retry + write_conflict audit
  L3 過期 expected 的 vu                 → conflict_flagged, branches=1, 主線版本不動, branch_created audit
  L4 再一次過期 vu                        → conflict_flagged, branches=2
  L5 第三次過期 vu（>MAX_BRANCHES=2）     → overflow_locked, locked=true, branch_overflow audit
  L6 鎖定後正確版本的 vu                  → MutationLawError(鎖定)；merge 仍可（metadata append 不受鎖）
  L7 全程單元過 schema（branches/locked 欄位擴充有效）→ PASS 或 WARN 皆可=非 FAIL
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mutation as mu
import pm_validate
from tests_phase1_base import BASE

results = []
AUDITS = []


def audit_fn(t, actor, details):
    AUDITS.append(t)


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# N1：no-op 拒升
try:
    mu.version_update(BASE, new_primitives={"state": BASE["dna"]["primitives"]["state"]}, change_summary="無變化")
    check("N1", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("N1", "MutationLawError", "MutationLawError")

# L1：正常提交
r = mu.write_with_lock(BASE, 1, "version_update", "instanceA", audit_fn,
                       new_primitives={"state": [{"dimension": "context", "value": "v2內容"}]},
                       change_summary="L1 正常升版")
unit_v2 = r["unit"]
check("L1", ("committed", 2), (r["status"], unit_v2["version"]["current_number"]))

# L2：過期 merge → 重放
r = mu.write_with_lock(unit_v2, 1, "merge", "instanceB", audit_fn, weight_dynamic_value=0.3)
check("L2", ("committed_after_retry", True), (r["status"], "write_conflict" in AUDITS))

# L3：過期 vu → 開分支
r = mu.write_with_lock(unit_v2, 1, "version_update", "instanceB", audit_fn,
                       new_primitives={"state": [{"dimension": "context", "value": "分支B"}]},
                       change_summary="L3 併發")
u = r["unit"]
check("L3", ("conflict_flagged", 1, 2, True),
      (r["status"], len(u["version"]["branches"]), u["version"]["current_number"], "branch_created" in AUDITS))

# L4：第二分支
r = mu.write_with_lock(u, 1, "version_update", "instanceC", audit_fn,
                       new_primitives={"state": [{"dimension": "context", "value": "分支C"}]},
                       change_summary="L4 併發")
u = r["unit"]
check("L4", ("conflict_flagged", 2), (r["status"], len(u["version"]["branches"])))

# L5：第三分支 → overflow
r = mu.write_with_lock(u, 1, "version_update", "instanceD", audit_fn,
                       new_primitives={"state": [{"dimension": "context", "value": "分支D"}]},
                       change_summary="L5 溢出")
u = r["unit"]
check("L5", ("overflow_locked", True, True),
      (r["status"], u["version"].get("locked", False), "branch_overflow" in AUDITS))

# L6：鎖定後 vu 拒、merge 可
try:
    mu.version_update(u, new_primitives={"state": [{"dimension": "context", "value": "鎖後"}]}, change_summary="不該過")
    l6a = "no-raise"
except mu.MutationLawError:
    l6a = "MutationLawError"
l6b = mu.merge(u, weight_dynamic_value=0.7)["weight"]["combined"]
check("L6", ("MutationLawError", 0.7), (l6a, l6b))

# L7：擴充欄位過 schema
v = pm_validate.validate_unit(u)
check("L7", True, v["status"] in ("PASS", "WARN"))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
