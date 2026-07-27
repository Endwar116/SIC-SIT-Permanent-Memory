#!/usr/bin/env python3
"""VS-9 Phase 7：Retriever 骨架＋喚醒引擎 v0.1（祖檔 Part 17）
[BOOTSTRAPPED]：semantic_similarity v1=關鍵詞重疊（無 embedding；E1 後換裝）。
排序權重 0.5/0.3/0.2 照 Part 17 公式形狀。
鐵律（ingest 規格 §五-2 承諾）：provenance.handshake_secret=true 一律召回豁免——
  HEC 測驗答案被一般檢索召回=交接驗證機制作廢。
side effect（Part 17）：top-k 命中寫 HitLedger；background 層命中且 Promotion Law 過
  → 回傳升層建議（不當場改單元——寫入是 store 層職責，此處只裁決）。
"""
from datetime import datetime

TOP_K = 5


def _tokens(text):
    return {t for t in text.replace("，", " ").replace("。", " ").split() if t} | set(text)


def _keyword_sim(query, unit):
    qt = _tokens(query)
    fields = []
    for e in unit["dna"]["primitives"]["entity"]:
        fields.append(str(e.get("value", "")))
    for s in unit["dna"]["primitives"]["state"]:
        fields.append(str(s.get("value", "")))
    ut = _tokens(" ".join(fields))
    if not qt or not ut:
        return 0.0
    return len(qt & ut) / len(qt | ut)


def _recency(unit, now):
    try:
        days = (now - datetime.fromisoformat(unit["version"]["updated_at"][:19])).days
    except Exception:
        return 0.0
    return max(0.0, 1.0 - days / 365)


def retrieve(query, units, ledger, session_id, instance_id, now_iso):
    """回傳 {results: top-k, promotions: 升層建議清單}。"""
    now = datetime.fromisoformat(now_iso[:19])
    scored = []
    for u in units:
        if u["provenance"].get("handshake_secret"):
            continue  # 召回豁免鐵律
        score = (_keyword_sim(query, u) * 0.5
                 + u["weight"]["combined"] * 0.3
                 + _recency(u, now) * 0.2)
        if score > 0:
            scored.append((u, round(score, 4)))
    scored.sort(key=lambda x: -x[1])
    top = scored[:TOP_K]

    promotions = []
    for u, score in top:
        ledger.record_hit(u["id"], now_iso, session_id, instance_id,
                          signals=["assembly"] if len(top) > 1 else [])
        if u["storage"]["layer"] == "background":
            verdict = ledger.should_promote(u["id"], now_iso)
            if verdict["promote"]:
                promotions.append({"unit_id": u["id"], "verdict": verdict,
                                   "action": "background→cache（Promotion Law 通過，交 store 執行+audit）"})
    return {"results": [{"id": u["id"], "score": s, "layer": u["storage"]["layer"]} for u, s in top],
            "promotions": promotions}
