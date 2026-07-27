#!/usr/bin/env python3
"""VS-9 Phase 7 測試：Promotion Law（T4/T5 場景）
預測（執行前落盤）：
  PR1 無命中                             → False（必要條件）
  PR2 91 天前的命中                       → False（窗外）
  PR3 同 session 刷 5 次 hit             → False（anti-gaming：獨立context=1，cross_session=1）＝T5
  PR4 兩個不同 session 各 1 hit          → True（cross_session=2）＝T4
  PR5 3 個獨立 context 帶 assembly       → True（assembly≥3）
  PR6 同 session 3 次 assembly           → False（獨立化後 assembly=1）
  PR7 單一 context 帶 task_context       → False（anti-gaming 底線：<2 獨立源）
  PR8 兩獨立 context 其一帶 task_context  → True
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from promotion import HitLedger

results = []
NOW = "2026-07-25T00:40:00"


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


L = HitLedger()
# PR1
check("PR1", False, L.should_promote("u1", NOW)["promote"])
# PR2
L.record_hit("u2", "2026-04-20T00:00:00", "s1", "i1")
check("PR2", False, L.should_promote("u2", NOW)["promote"])
# PR3（T5）
for _ in range(5):
    L.record_hit("u3", "2026-07-24T10:00:00", "s1", "i1")
r3 = L.should_promote("u3", NOW)
check("PR3", (False, 1), (r3["promote"], r3["independent_contexts"]))
# PR4（T4）
L.record_hit("u4", "2026-07-23T10:00:00", "s1", "i1")
L.record_hit("u4", "2026-07-24T10:00:00", "s2", "i1")
r4 = L.should_promote("u4", NOW)
check("PR4", (True, 2), (r4["promote"], r4["cross_session"]))
# PR5
for k in range(3):
    L.record_hit("u5", "2026-07-24T10:00:00", f"s{k}", "i1", signals=["assembly"])
r5 = L.should_promote("u5", NOW)
check("PR5", (True, 3), (r5["promote"], r5["assembly_independent"]))
# PR6
for _ in range(3):
    L.record_hit("u6", "2026-07-24T10:00:00", "s1", "i1", signals=["assembly"])
r6 = L.should_promote("u6", NOW)
check("PR6", (False, 1), (r6["promote"], r6["assembly_independent"]))
# PR7
L.record_hit("u7", "2026-07-24T10:00:00", "s1", "i1", signals=["task_context"])
check("PR7", False, L.should_promote("u7", NOW)["promote"])
# PR8
L.record_hit("u8", "2026-07-24T10:00:00", "s1", "i1", signals=["task_context"])
L.record_hit("u8", "2026-07-24T11:00:00", "s2", "i1")
check("PR8", True, L.should_promote("u8", NOW)["promote"])

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
