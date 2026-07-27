#!/usr/bin/env python3
"""VS-9 Phase 4 測試：Pre-Memory Gate（R-7 語義=T 核心）
預測（執行前落盤）：
  G1 正常文字                    → PASS＋verbatim 可讀回原文
  G2 噪音（「。。。」）           → DISCARD＋**verbatim 仍讀得回**（R-7 核心：擋結構不擋原料）
  G3 同信號第 4 次               → AGGREGATE, counter=4
  G4 同信號第 11 次              → ANOMALY, counter=11＋anomaly_flag audit
  【首跑記錄】G4 初版預測 counter=12=算術 off-by-one（首見=1，第11次=11），5/6；程式行為正確，修正的是預測
  G5 window 淘汰後同信號         → 不聚合（window 只看最近 50）——用小窗模擬
  G6 verbatim 總條數 = 全部輸入數（含 DISCARD/AGGREGATE 的原文，一條不少）
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import verbatim_store as vs

TESTDATA = Path(__file__).parent / "data_test_g"
vs.DATA, vs.SEGS, vs.KEYS = TESTDATA, TESTDATA / "verbatim", TESTDATA / "keys"
vs.AUDIT, vs.REGISTRY = TESTDATA / "audit.jsonl", TESTDATA / "keys" / "keys_registry.json"
if TESTDATA.exists():
    _old = TESTDATA.parent / "data_test_g_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TESTDATA), str(_old / f"run_{len(list(_old.iterdir()))}"))

import gate

results, AUDITS = [], []
g = gate.PreMemoryGate(audit_fn=lambda t, a, d: AUDITS.append(t))
SEG = "2026-07G"
total_inputs = 0


def feed(text):
    global total_inputs
    total_inputs += 1
    return g.process(text, segment=SEG)


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


# G1
r = feed("使用者今天確認了封存範圍的問題。")
check("G1", ("PASS", "使用者今天確認了封存範圍的問題。"),
      (r["action"], vs.read(SEG, r["verbatim"]["seq"])))
# G2
r = feed("。。。")
check("G2", ("DISCARD", "。。。"), (r["action"], vs.read(SEG, r["verbatim"]["seq"])))
# G3/G4
last = None
for i in range(11):
    last = feed("說要死但沒死。")
    if i == 3:
        g3 = last
check("G3", ("AGGREGATE", 4), (g3["action"], g3["counter"]))
check("G4", ("ANOMALY", 11, True), (last["action"], last["counter"], "anomaly_flag" in AUDITS))
# G5：小窗模擬淘汰
import collections
g2 = gate.PreMemoryGate()
g2.window = collections.deque(maxlen=3)
for t in ["甲", "乙", "丙", "丁"]:  # 「甲」被擠出窗
    g2.process(t, segment=SEG); total_inputs += 1
r = g2.process("甲", segment=SEG); total_inputs += 1
check("G5", "PASS", r["action"])
# G6
v = vs.verify_chain(SEG)
check("G6", (True, total_inputs), (v["ok"], v["entries"]))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
