#!/usr/bin/env python3
"""VS-9 Phase 7b 測試：Retriever＋喚醒端到端（T4 全鏈路）
預測（執行前落盤）：
  R1 查詢命中 entity 值 → 該單元排第一
  R2 handshake_secret 單元即使全字命中 → 不出現在結果（召回豁免鐵律）
  R3 T4 端到端：background 單元被兩個不同 session 各檢索一次 → 第二次回傳升層建議
  R4 T5 端到端：同 session 連查 5 次 → 永無升層建議
  R5 每次 retrieve 都記帳：ledger 命中數 = retrieve 次數（對該單元）
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import retriever
from promotion import HitLedger
from tests_phase1_base import BASE

results = []
NOW = "2026-07-25T01:40:00"


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


def mk(uid, value, layer="background", secret=False):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["dna"]["primitives"]["entity"][0]["value"] = value
    u["storage"]["layer"] = layer
    u["provenance"]["handshake_secret"] = secret
    u["version"]["updated_at"] = "2026-07-24T00:00:00"
    return u


units = [mk("mu-pm", "永久記憶系統"), mk("mu-vj", "SIC-VJ視覺"), mk("mu-sec", "永久記憶系統", secret=True)]

# R1+R2
L = HitLedger()
r = retriever.retrieve("永久記憶系統 的 設計", units, L, "s1", "i1", NOW)
ids = [x["id"] for x in r["results"]]
check("R1", "mu-pm", ids[0])
check("R2", False, "mu-sec" in ids)

# R3（T4）：兩個 session
L2 = HitLedger()
u = [mk("mu-t4", "治理示範")]
r1 = retriever.retrieve("治理示範", u, L2, "sA", "i1", NOW)
r2 = retriever.retrieve("治理示範", u, L2, "sB", "i1", NOW)
check("R3", (0, 1), (len(r1["promotions"]), len(r2["promotions"])))

# R4（T5）：同 session 刷 5 次
L3 = HitLedger()
u5 = [mk("mu-t5", "刷分測試")]
promos = 0
for _ in range(5):
    promos += len(retriever.retrieve("刷分測試", u5, L3, "s1", "i1", NOW)["promotions"])
check("R4", 0, promos)

# R5：記帳數
check("R5", 5, len(L3.hits["mu-t5"]))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
