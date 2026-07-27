#!/usr/bin/env python3
"""VS-9 Phase 5b 測試：衝突解決（T2/T3 場景）
預測（執行前落盤）：
  C1 同entity同dimension異值→True；異entity→False
  C2 signed vault vs 無簽 cache               → signed 勝（resolution=signed_source）
  C3 anchor vs anchor                         → non_auto（top_vs_top）＋write_conflict audit＋無勝負方
  C4 task(S2) vs episodic(S5)                 → task 勝（source_confidence）
  C5 全同級但 b 較新                           → b 勝（time）
  C6 敗方=superseded：降background＋conflict_supersede audit＋原單元完整存在（不刪）
  C7 intent 方向相反（approve vs reject）      → non_auto（intent_opposite）
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import conflict as cf
from tests_phase1_base import BASE

results, AUDITS = [], []


def audit_fn(t, a, d):
    AUDITS.append(t)


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


def mk(uid, kind="episodic", layer="cache", signed=False, state_val="X", entity_id="e1",
       updated="2026-07-24T10:00:00", weight=0.1, intent=None, retention="deletable", history=None):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["memory_kind"] = kind
    u["foundational"] = kind == "anchor"
    u["storage"]["layer"] = layer
    u["storage"]["retention_class"] = "immutable" if (signed or kind == "anchor") else retention
    if signed:
        u["storage"]["integrity_signature"] = {"algorithm": "Ed25519", "signed_fields": ["id"],
                                               "signature": "sig", "signed_at": "t", "signer": "system"}
    u["dna"]["primitives"]["entity"][0]["id"] = entity_id
    u["dna"]["primitives"]["state"][0]["value"] = state_val
    u["dna"]["primitives"]["intent"] = intent
    u["version"]["updated_at"] = updated
    u["version"]["history"] = history or []
    u["weight"]["combined"] = weight
    return u


# C1
a = mk("mu-a1", state_val="開")
b = mk("mu-b1", state_val="關")
c = mk("mu-c1", state_val="開", entity_id="e2")
check("C1", (True, False), (cf.detect_conflict(a, b), cf.detect_conflict(a, c)))
# C2
sv = mk("mu-sv", kind="semantic", layer="vault", signed=True, state_val="開")
un = mk("mu-un", kind="semantic", layer="cache", state_val="關")
rec, w, l = cf.arbitrate(sv, un, audit_fn)
check("C2", ("mu-sv", "signed_source"), (w["id"], rec["resolution"]))
# C3
a1 = mk("mu-an1", kind="anchor", layer="vault", signed=True, state_val="開")
a2 = mk("mu-an2", kind="anchor", layer="vault", signed=True, state_val="關")
rec3, w3, l3 = cf.arbitrate(a1, a2, audit_fn)
check("C3", ("human", False, None, True),
      (rec3["resolution"], rec3["auto_arbitrable"], w3, "write_conflict" in AUDITS))
# C4
t = mk("mu-task", kind="task", state_val="開")
e = mk("mu-epi", kind="episodic", state_val="關")
rec4, w4, _ = cf.arbitrate(t, e, audit_fn)
check("C4", ("mu-task", "source_confidence"), (w4["id"], rec4["resolution"]))
# C5
old = mk("mu-old", updated="2026-07-20T00:00:00", state_val="開")
new = mk("mu-new", updated="2026-07-24T00:00:00", state_val="關")
rec5, w5, _ = cf.arbitrate(old, new, audit_fn)
check("C5", ("mu-new", "time"), (w5["id"], rec5["resolution"]))
# C6
_, w6, sup6 = cf.arbitrate(t, e, audit_fn)
check("C6", ("background", "conflict_supersede", "mu-epi", True),
      (sup6["storage"]["layer"], sup6["audit_trail"][-1]["audit_type"], sup6["id"],
       "conflict_supersede" in AUDITS and e["storage"]["layer"] == "cache"))  # 原單元不動=不刪
# C7
ia = mk("mu-ia", intent=[{"actor": "e1", "direction": "approve"}], state_val="開")
ib = mk("mu-ib", intent=[{"actor": "e1", "direction": "reject"}], state_val="關")
rec7, w7, _ = cf.arbitrate(ia, ib, audit_fn)
check("C7", ("human", "intent_opposite"), (rec7["resolution"], rec7["why"]))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
