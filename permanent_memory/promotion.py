#!/usr/bin/env python3
"""VS-9 Phase 7：Promotion Law v0.1（祖檔 Part 10＋errata #5 anti-gaming）
核心命題：被查到 ≠ 值得升層。
  必要條件：90 天內有 retrieval hit
  充分條件（至少一）：new_relation / task_context / cross_session≥2 / assembly_count≥3
  Anti-gaming [FROZEN]：promotion 證據須來自 ≥2 獨立 context（不同 session_id 或 instance_id）；
  同 session、同任務鏈的 signal 只計一次——「而你就是那個可能作弊的 agent」（設計史 §4.5：這條規則是防我的）。
CACHE_PROMOTION_THRESHOLD 不存在（Q2 建議廢名）：本模組用的就是 Part 10 布林組合＋兩個硬編參數。
"""
from datetime import datetime, timedelta

RETRIEVAL_WINDOW_DAYS = 90   # Part 10.2
CROSS_SESSION_MIN = 2        # Part 10.2 硬編參數（E4 重校準對象）
ASSEMBLY_MIN = 3             # Part 10.2 硬編參數（E4 重校準對象）


class HitLedger:
    """檢索命中帳（外部 store 介面的記憶體版）。"""

    def __init__(self):
        self.hits = {}  # unit_id → [ {ts, session_id, instance_id, signals:set} ]

    def record_hit(self, unit_id, ts, session_id, instance_id, signals=()):
        self.hits.setdefault(unit_id, []).append(
            {"ts": ts, "session_id": session_id, "instance_id": instance_id, "signals": set(signals)})

    def _independent(self, entries):
        """errata #5：獨立 context = 不同 session_id 或 instance_id；同組只計一次。"""
        seen, out = set(), []
        for e in entries:
            key = (e["session_id"], e["instance_id"])
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    def should_promote(self, unit_id, now_iso, has_new_relation=False):
        entries = self.hits.get(unit_id, [])
        now = datetime.fromisoformat(now_iso)
        cutoff = now - timedelta(days=RETRIEVAL_WINDOW_DAYS)
        recent = [e for e in entries if datetime.fromisoformat(e["ts"]) >= cutoff]
        if not recent:
            return {"promote": False, "why": "無 90 天內 retrieval hit（必要條件不成立）"}

        indep = self._independent(recent)
        cross_session = len({(e["session_id"], e["instance_id"]) for e in recent})
        assembly = sum(1 for e in indep if "assembly" in e["signals"])
        task_ctx = any("task_context" in e["signals"] for e in indep)

        structural = (
            has_new_relation
            or task_ctx
            or cross_session >= CROSS_SESSION_MIN
            or assembly >= ASSEMBLY_MIN
        )
        # anti-gaming 底線：無論哪條充分條件成立，證據都須 ≥2 獨立 context
        if structural and len(indep) < 2 and not has_new_relation:
            return {"promote": False, "why": f"anti-gaming：獨立 context={len(indep)}<2（同源 signal 只計一次）",
                    "independent_contexts": len(indep)}
        return {"promote": bool(structural), "independent_contexts": len(indep),
                "cross_session": cross_session, "assembly_independent": assembly,
                "why": "retrieval_hit + structural_usefulness" if structural else "有命中但無結構性有用性"}
