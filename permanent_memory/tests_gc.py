#!/usr/bin/env python3
"""VS-9 GC 治理式測試（GC 禁區鐵律實測）
預測（執行前落盤）：
  GC1 background 低權重(0.08) → folded＋gc_compress audit
  GC2 更低(0.02) → skeleton_only＋fold_summary 清空＋primitives 原封不動
  GC3 豁免四型（anchor/immutable/foundational/cache層）→ 全不動
  GC4 GC 前後 verbatim 條數與鏈完全不變（禁區實測）
  GC5 purge 非 human → PermissionError＋bap_reject；human＋policy → shred 完成＋雙 audit＋讀取拒
  GC6 已壓縮者不回升（冪等：第二輪 GC untouched）
"""
import copy, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import verbatim_store as vs
TD = Path(__file__).parent / "data_test_gc"
vs.DATA, vs.SEGS, vs.KEYS = TD, TD / "verbatim", TD / "keys"
vs.AUDIT, vs.REGISTRY = TD / "audit.jsonl", TD / "keys" / "keys_registry.json"
if TD.exists():
    _old = TD.parent / "data_test_gc_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TD), str(_old / f"run_{len(list(_old.iterdir()))}"))
import gc_governed as gcg
from store import MemoryStore
from tests_phase1_base import BASE

results = []
def check(name, expect, got):
    ok = expect == got; results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")

def mk(uid, w, layer="background", kind="episodic", retention="deletable", foundational=False, state_val=None):
    u = copy.deepcopy(BASE); u["id"] = uid
    u["memory_kind"] = kind; u["foundational"] = foundational or kind == "anchor"
    u["storage"]["layer"] = layer
    u["storage"]["retention_class"] = "immutable" if kind == "anchor" else retention
    u["weight"]["dynamic"]["value"] = w; u["weight"]["combined"] = w
    u["dna"]["primitives"]["state"][0]["value"] = state_val or f"GC測試單元 {uid} 的獨立內容敘述，避免互相被去重收編，權重{w}"
    u["semantic_fold"]["fold_summary"] = {"summary": f"{uid} 摘要"}
    return u

S = MemoryStore(TD / "store")
for spec in [("mu-gc0fold0", 0.08, {}), ("mu-gc0skel0", 0.02, {}),
             ("mu-gc0anch0", 0.01, {"kind": "anchor"}),
             ("mu-gc0immu0", 0.01, {"retention": "immutable"}),
             ("mu-gc0found", 0.01, {"foundational": True}),
             ("mu-gc0cache", 0.01, {"layer": "cache"})]:
    uid, w, kw = spec
    S._persist(mk(uid, w, **kw))  # 直接佈置（繞 dedup 場景搭建）

# 原文佈置
for i in range(3): vs.append(f"GC 禁區測試原文第{i}條", segment="2026-07G6")
before = vs.verify_chain("2026-07G6")

r1 = gcg.run_gc(S)
u_fold = S.get("mu-gc0fold0"); u_skel = S.get("mu-gc0skel0")
audits = [json.loads(l)["audit_type"] for l in open(S.audit_path, encoding="utf-8")]
check("GC1", ("folded", True), (u_fold["storage"]["compression_state"], "gc_compress" in audits))
check("GC2", ("skeleton_only", {}, "GC測試單元 mu-gc0skel0 的獨立內容敘述，避免互相被去重收編，權重0.02"),
      (u_skel["storage"]["compression_state"], u_skel["semantic_fold"]["fold_summary"],
       u_skel["dna"]["primitives"]["state"][0]["value"]))
untouched_ids = [S.get(x)["storage"]["compression_state"] for x in
                 ("mu-gc0anch0", "mu-gc0immu0", "mu-gc0found", "mu-gc0cache")]
check("GC3", ["none"] * 4, untouched_ids)
after = vs.verify_chain("2026-07G6")
check("GC4", (before["entries"], before["head"], True), (after["entries"], after["head"], after["ok"]))
# GC5
try:
    gcg.purge_verbatim(S, "2026-07G6", actor="system", policy_ref="P-TEST")
    g5a = "no-raise"
except PermissionError:
    g5a = "PermissionError"
pr = gcg.purge_verbatim(S, "2026-07G6", actor="human", policy_ref="P-TEST-001（人工模擬授權）")
try:
    vs.read("2026-07G6", 0); g5b = "readable!"
except vs.SegmentShredded:
    g5b = "SegmentShredded"
audits2 = [json.loads(l)["audit_type"] for l in open(S.audit_path, encoding="utf-8")]
check("GC5", ("PermissionError", "SegmentShredded", True, True),
      (g5a, g5b, "bap_reject" in audits2, "purge_policy_invoked" in audits2))
# GC6 冪等
r2 = gcg.run_gc(S)
check("GC6", 0, len(r2["compressed"]))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
