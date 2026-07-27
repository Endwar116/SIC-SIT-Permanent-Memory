#!/usr/bin/env python3
"""VS-9 Phase 2c 測試：權重衰減（E4 定性判準）＋分支仲裁（F9 修）
預測（執行前落盤）：
  W1 real_impact 階梯（決策變更0.8/高權引用0.6/任務鏈0.5/新關係0.4/僅查詢0.1）→ 全對
  D1 「說要死沒死」×30（0.5, rate 0.1）      → <0.03 且 >0（趨近0，E4 定性判準過）
  D2 signal_count=1                          → 不衰減（0.5）
  D3 極端 count=1000                          → >=0（下限保護）
  B1 overflow 鎖定下非 human 仲裁             → MutationLawError + bap_reject audit
  B2 human 仲裁勝方分支                       → 版本+1、branches清空、locked=False、branch_merged audit 含敗方提案
  B3 勝方提案含終態 task 但無 ruling_audit_id  → MutationLawError（F12 重檢生效）
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mutation as mu
import weights as wt
from tests_phase1_base import BASE

results, AUDITS = [], []


def audit_fn(t, actor, details):
    AUDITS.append((t, details))


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# W1
check("W1", (0.8, 0.6, 0.5, 0.4, 0.1), (
    wt.real_impact(led_to_decision_change=True),
    wt.real_impact(referenced_by_high_weight=True),
    wt.real_impact(in_task_execution_chain=True),
    wt.real_impact(created_new_relation=True),
    wt.real_impact()))
# D1
v30 = wt.apply_decay_on_repeat(0.5, 30)
check("D1", True, 0 < v30 < 0.03)
# D2
check("D2", 0.5, wt.apply_decay_on_repeat(0.5, 1))
# D3
check("D3", True, wt.apply_decay_on_repeat(0.5, 1000) >= 0)


def make_locked_unit():
    """重建 L5 溢出情境：v2 主線 + 3 分支 + locked"""
    r = mu.write_with_lock(BASE, 1, "version_update", "A", audit_fn,
                           new_primitives={"state": [{"dimension": "context", "value": "主線v2"}]},
                           change_summary="主線")
    u = r["unit"]
    for i, val in enumerate(["分支B", "分支C", "分支D"]):
        r = mu.write_with_lock(u, 1, "version_update", f"inst{i}", audit_fn,
                               new_primitives={"state": [{"dimension": "context", "value": val}]},
                               change_summary=f"併發{val}")
        u = r["unit"]
    return u


# B1
u = make_locked_unit()
try:
    mu.resolve_branches(u, "branch-1", actor="system", audit_fn=audit_fn)
    check("B1", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("B1", "MutationLawError", "MutationLawError" if any(a[0] == "bap_reject" for a in AUDITS) else "raise-no-audit")

# B2
u2 = mu.resolve_branches(u, "branch-2", actor="human", audit_fn=audit_fn)
merged = [a for a in AUDITS if a[0] == "branch_merged"]
check("B2", (3, 0, False, True, 2),
      (u2["version"]["current_number"], len(u2["version"]["branches"]),
       u2["version"].get("locked"), len(merged) == 1,
       len(merged[0][1]["losers_superseded"]) if merged else -1))

# B3
u = make_locked_unit()
u["version"]["branches"][0]["proposed"]["new_primitives"] = {
    "task": {"id": "VS-9", "title": "t", "deliverable": "d", "status": "completed", "created_round": 1}}
try:
    mu.resolve_branches(u, "branch-1", actor="human", audit_fn=audit_fn)
    check("B3", "MutationLawError", "no-raise")
except mu.MutationLawError:
    check("B3", "MutationLawError", "MutationLawError")

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
