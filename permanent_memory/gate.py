#!/usr/bin/env python3
"""VS-9 Phase 4：Pre-Memory Gate v0.1（祖檔 Part 16＋R-7 生效語義＋P-13）
R-7 鐵律：**DISCARD 只作用於「不生成 memory_unit」，verbatim 照收。**
  閘門擋的是結構的生成，不是原料的保存——所有輸入先落 verbatim（append-only、加密段檔），
  Gate 判定只決定是否進入 Semantic Fold。
頻率聚合（Part 16）：window(50) 內同信號 >3 → AGGREGATE（掛 counter，不重複生成結構）；
  同類 >10 → ANOMALY FLAG（高頻異常反而升級標記，不靜默）。
[BOOTSTRAPPED]：相似度 v1=正規化後精確比對（無 embedding；E1 之後才有語義相似度）。
"""
import re
import unicodedata
from collections import deque

import verbatim_store as vs

WINDOW = 50          # Part 16 原文
AGG_THRESHOLD = 3    # similar in window > 3 → AGGREGATE
ANOMALY_THRESHOLD = 10  # 超過 10 條同類 → ANOMALY FLAG

_NOISE = re.compile(r"^[\s。．.、，,!?！？~～\-=+*#]*$")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip().lower()


class PreMemoryGate:
    def __init__(self, audit_fn=None):
        self.window = deque(maxlen=WINDOW)
        self.counters = {}  # norm → count（聚合計數；首條 loc 一併記）
        self.audit_fn = audit_fn or (lambda *a, **k: None)

    def process(self, text: str, ts: str | None = None, segment: str | None = None) -> dict:
        """R-7 順序：先 verbatim 落地，再判結構。回傳 {action, verbatim, counter?}。"""
        loc = vs.append(text, ts=ts, segment=segment)  # 原料無條件保存（R-7）

        norm = _norm(text)
        if not norm or _NOISE.match(text):
            return {"action": "DISCARD", "verbatim": loc,
                    "note": "noise/trivial：不生成 memory_unit；原文已保存"}

        similar_in_window = sum(1 for n in self.window if n == norm)
        self.window.append(norm)

        if similar_in_window > 0:
            entry = self.counters.setdefault(norm, {"count": 1, "first": None})
            entry["count"] += 1
            if entry["first"] is None:
                entry["first"] = loc
            if entry["count"] > ANOMALY_THRESHOLD:
                self.audit_fn("anomaly_flag", "system",
                              {"signal_count": entry["count"], "verbatim": loc,
                               "note": "高頻異常升級標記，不靜默丟棄"})
                return {"action": "ANOMALY", "verbatim": loc, "counter": entry["count"]}
            if similar_in_window >= AGG_THRESHOLD:
                return {"action": "AGGREGATE", "verbatim": loc, "counter": entry["count"],
                        "note": "聚合至首條+counter，不重複生成結構"}

        return {"action": "PASS", "verbatim": loc,
                "note": "進 Semantic Fold（六原語抽取=Phase 5+ 範圍）"}
