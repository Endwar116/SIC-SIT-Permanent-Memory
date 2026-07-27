#!/usr/bin/env python3
"""VS-9 Phase 1 自驗測試（R14：預測寫死在此，跑完對照）
預測（執行前落盤）：
  S1 完整合法單元(dyad null+task null)      → PASS
  S2 primitives 缺 task key                → FAIL(schema)   # fail-closed
  S3 task 終態無裁定 audit                  → FAIL(R-2)
  S4 anchor 但 foundational=false          → FAIL(anchor)
  S5 cache 層帶簽名                         → FAIL(signature)
  S6 handshake_secret=true                 → WARN(retrieval)
  V1 寫3條→逐條解密==原文                    → True
  V2 verify_chain                          → ok, entries=3
  V3 shred(actor=system)                   → PermissionError + bap_reject audit
  V4 shred(actor=human)→read               → SegmentShredded
  V5 shred 後 verify_chain（無金鑰）         → 仍 ok（T12 核心）
  V6 audit 含 delete_attempt+retention_change, registry=shredded → True
"""
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pm_validate
import verbatim_store as vs

# 測試用隔離資料區
TESTDATA = Path(__file__).parent / "data_test"
for attr, sub in [("DATA", ""), ("SEGS", "verbatim"), ("KEYS", "keys")]:
    setattr(vs, attr, TESTDATA / sub if sub else TESTDATA)
vs.AUDIT = TESTDATA / "audit.jsonl"
vs.REGISTRY = TESTDATA / "keys" / "keys_registry.json"
if TESTDATA.exists():
    _old = TESTDATA.parent / "data_test_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TESTDATA), str(_old / f"run_{len(list(_old.iterdir()))}"))  # AGR：不rm，移舊（唯一序號防撞，R221修）

from tests_phase1_base import BASE  # 共用基準單元

results = []


def check(name, expect, got):
    ok = expect == got
    results.append((name, expect, got, ok))
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# S1
check("S1", "PASS", pm_validate.validate_unit(BASE)["status"])
# S2
u = copy.deepcopy(BASE); del u["dna"]["primitives"]["task"]
check("S2", "FAIL", pm_validate.validate_unit(u)["status"])
# S3
u = copy.deepcopy(BASE)
u["dna"]["primitives"]["task"] = {"id": "VS-9", "title": "t", "deliverable": "d", "status": "completed", "created_round": 1}
check("S3", "FAIL", pm_validate.validate_unit(u)["status"])
# S4
u = copy.deepcopy(BASE); u["memory_kind"] = "anchor"; u["storage"]["retention_class"] = "immutable"
check("S4", "FAIL", pm_validate.validate_unit(u)["status"])
# S5
u = copy.deepcopy(BASE)
u["storage"]["integrity_signature"] = {"algorithm": "Ed25519", "signed_fields": ["id"], "signature": "x", "signed_at": "t", "signer": "system"}
check("S5", "FAIL", pm_validate.validate_unit(u)["status"])
# S6
u = copy.deepcopy(BASE); u["provenance"]["handshake_secret"] = True
check("S6", "WARN", pm_validate.validate_unit(u)["status"])

# V1 roundtrip
texts = ["第一條原文：使用者說要記得。", "第二條：failure 也要記。", "第三條：測 shred。"]
locs = [vs.append(t, ts="2026-07-24T13:40:00", segment="2026-07T") for t in texts]
check("V1", True, all(vs.read("2026-07T", loc["seq"]) == t for t, loc in zip(texts, locs)))
# V2
v = vs.verify_chain("2026-07T")
check("V2", (True, 3), (v["ok"], v["entries"]))
# V3
try:
    vs.shred("2026-07T", actor="system", reason="test")
    check("V3", "PermissionError", "no-raise")
except PermissionError:
    bap = any(json.loads(l)["audit_type"] == "bap_reject" for l in open(vs.AUDIT, encoding="utf-8"))
    check("V3", "PermissionError", "PermissionError" if bap else "raise-but-no-audit")
# V4
vs.shred("2026-07T", actor="human", reason="R-12 測試：被遺忘權演練")
try:
    vs.read("2026-07T", 0)
    check("V4", "SegmentShredded", "readable!")
except vs.SegmentShredded:
    check("V4", "SegmentShredded", "SegmentShredded")
# V5
v = vs.verify_chain("2026-07T")
check("V5", (True, 3), (v["ok"], v["entries"]))
# V6
audits = [json.loads(l)["audit_type"] for l in open(vs.AUDIT, encoding="utf-8")]
reg = json.load(open(vs.REGISTRY, encoding="utf-8"))
check("V6", True, "delete_attempt" in audits and "retention_change" in audits and reg["2026-07T"]["status"] == "shredded")

hits = sum(1 for r in results if r[3])
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
