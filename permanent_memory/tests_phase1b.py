#!/usr/bin/env python3
"""VS-9 Phase 1b 測試：補紅隊 F2（鏈頭外錨）與 F3（覆蓋缺口）
預測（執行前落盤）：
  S7 anchor + foundational=true + retention=deletable  → FAIL(anchor)   # F3 缺口一
  S8 vault 層無簽名                                     → FAIL(vault)    # F3 缺口二
  C1 checkpoint 後 verify_against_checkpoint            → ok=True
  C2 砍尾（移走最後一行）後 verify_chain                 → 仍 ok=True（盲區實證：F2 存在）
  C3 同狀態 verify_against_checkpoint                   → ok=False（外錨抓到砍尾）
"""
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pm_validate
import verbatim_store as vs

TESTDATA = Path(__file__).parent / "data_test_b"
vs.DATA, vs.SEGS, vs.KEYS = TESTDATA, TESTDATA / "verbatim", TESTDATA / "keys"
vs.AUDIT, vs.REGISTRY = TESTDATA / "audit.jsonl", TESTDATA / "keys" / "keys_registry.json"
if TESTDATA.exists():
    _old = TESTDATA.parent / "data_test_b_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TESTDATA), str(_old / f"run_{len(list(_old.iterdir()))}"))  # 唯一序號防撞（R221修）

import tests_phase1_base as tb

results = []


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# S7：anchor + foundational=true 但 deletable
u = copy.deepcopy(tb.BASE)
u["memory_kind"] = "anchor"; u["foundational"] = True; u["storage"]["retention_class"] = "deletable"
check("S7", "FAIL", pm_validate.validate_unit(u)["status"])

# S8：vault 層無簽名
u = copy.deepcopy(tb.BASE)
u["storage"]["layer"] = "vault"; u["storage"]["retention_class"] = "immutable"
check("S8", "FAIL", pm_validate.validate_unit(u)["status"])

# C1：三條 → checkpoint → 對錨驗證
for i in range(3):
    vs.append(f"外錨測試第{i}條", segment="2026-07C")
vs.checkpoint("2026-07C")
check("C1", True, vs.verify_against_checkpoint("2026-07C")["ok"])

# C2/C3：砍尾攻擊（append-only 違規模擬）
seg = vs._seg_file("2026-07C")
lines = seg.read_text(encoding="utf-8").splitlines()
seg.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # 移走最後一行
check("C2_盲區實證", True, vs.verify_chain("2026-07C")["ok"])
check("C3_外錨抓到", False, vs.verify_against_checkpoint("2026-07C")["ok"])

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
