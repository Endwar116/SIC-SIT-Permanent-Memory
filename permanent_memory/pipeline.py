#!/usr/bin/env python3
"""VS-9：端到端寫入流水線 v0.1（Gate → Verbatim → Fold掛載 → Store）
一句話進來 → 原文無條件加密落盤（R-7）→ Gate 判結構 → 過了才組 memory_unit
（semantic_fold.original_ref 指回 verbatim 段位）→ store 寫入管線（驗證/去重/治理）。
六原語抽取（Semantic Fold 本體）是執行期 AI 的工作，本層接收已折疊的 primitives。
"""


class Pipeline:
    def __init__(self, gate, memstore):
        self.gate = gate
        self.store = memstore

    def ingest(self, text, unit=None, ts=None, segment=None, actor="system"):
        """回傳 {gate_action, verbatim, store_result|None}。unit=None 或 Gate 未 PASS 時只保原文。"""
        g = self.gate.process(text, ts=ts, segment=segment)
        if g["action"] != "PASS" or unit is None:
            return {"gate_action": g["action"], "verbatim": g["verbatim"], "store_result": None}
        unit["semantic_fold"]["original_ref"] = f"{g['verbatim']['segment']}:{g['verbatim']['seq']}"
        return {"gate_action": "PASS", "verbatim": g["verbatim"],
                "store_result": self.store.write(unit, actor=actor)}
