#!/usr/bin/env python3
"""VS-9 Phase 5：記憶衝突解決 v0.1（祖檔 Part 12＋Part 11 兩段式 Source Confidence＋errata #6）
鐵則：衝突不刪除任何一方——敗方標 superseded 降 background，原文永在。
不可自動仲裁（直接進人工隊列）：頂級對頂級（anchor vs anchor / vs signed vault）、
intent 方向相反、主觀 relational 判斷（v1 以 relational-vs-relational 無客觀依據近似）。
"""
import copy
import uuid
from datetime import datetime, timezone

# Part 11 第一段：Source Type（v1 由 memory_kind 導出；inferred/aggregate 屬 Phase 7 聚合層暫缺）
SOURCE_LEVEL = {"anchor": 1, "task": 2, "semantic": 3, "relational": 4, "episodic": 5}
STALENESS_DAYS = 365  # [BOOTSTRAPPED] E4 校準對象（同 foundational_gate）


def _now():
    return datetime.now(timezone.utc).isoformat()


def is_signed_vault(u):
    return u["storage"]["layer"] == "vault" and u["storage"]["integrity_signature"] is not None


def effective_level(u, days_since_last_reference=0):
    """Part 11 兩段式：Source Type ± Modifiers。數字小=信任高。"""
    lvl = SOURCE_LEVEL.get(u["memory_kind"], 5)
    if is_signed_vault(u):
        lvl -= 2  # signed_vault_bonus
    if days_since_last_reference > STALENESS_DAYS and not u["foundational"]:
        lvl += 1  # staleness_penalty（foundational 豁免；上限只降一次）
    if u["storage"]["layer"] == "background":
        lvl += 1  # background_penalty
    return lvl


def detect_conflict(a, b):
    """同 entity＋重疊 state dimension＋矛盾值。"""
    ea = {e["id"] for e in a["dna"]["primitives"]["entity"]}
    eb = {e["id"] for e in b["dna"]["primitives"]["entity"]}
    if not (ea & eb):
        return False
    sa = {s["dimension"]: s["value"] for s in a["dna"]["primitives"]["state"]}
    sb = {s["dimension"]: s["value"] for s in b["dna"]["primitives"]["state"]}
    shared = set(sa) & set(sb)
    return any(sa[d] != sb[d] for d in shared)


def _non_auto(a, b, la, lb):
    """errata #6 清單（含原設計者 2026-07-25 澄清）。"""
    # anchor vs 任何 signed vault：兩種不同質的最高權威（人工憲法 vs 密碼學），
    # 效值不等也不代表系統有權替人類選邊——一律人工（設計者原始意圖）。
    if (a["memory_kind"] == "anchor") != (b["memory_kind"] == "anchor"):
        other = b if a["memory_kind"] == "anchor" else a
        if is_signed_vault(other):
            return "anchor_vs_signed_vault"
    if la == lb and la <= 1:
        return "top_vs_top"
    ia, ib = a["dna"]["primitives"]["intent"], b["dna"]["primitives"]["intent"]
    if ia and ib:
        da = {i.get("direction") for i in ia}
        db = {i.get("direction") for i in ib}
        opposite = {("approve", "reject"), ("reject", "approve"), ("keep", "delete"), ("delete", "keep")}
        if any((x, y) in opposite for x in da for y in db):
            return "intent_opposite"
    if a["memory_kind"] == "relational" and b["memory_kind"] == "relational":
        return "relational_subjective"
    return None


def arbitrate(a, b, audit_fn, days_ref_a=0, days_ref_b=0):
    """Part 12 六級仲裁梯。回傳 (conflict_record, winner, superseded_loser)；non_auto 時後兩者為 None。"""
    la, lb = effective_level(a, days_ref_a), effective_level(b, days_ref_b)

    na = _non_auto(a, b, la, lb)
    rec = {"conflict_id": str(uuid.uuid4()), "resolved_at": _now()}
    if na:
        rec.update({"memory_a": a["id"], "memory_b": b["id"], "resolution": "human",
                    "auto_arbitrable": False, "resolved_by": None, "why": na})
        audit_fn("write_conflict", "system", {"conflict_id": rec["conflict_id"], "non_auto": na,
                                              "action": "進 arbitration 人工隊列"})
        return rec, None, None

    # 1 signed vault → 2 effective level → 3 版本鏈 → 4 時間 → 5 權重 → 6 human
    def pick():
        if is_signed_vault(a) != is_signed_vault(b):
            return (a, b, "signed_source") if is_signed_vault(a) else (b, a, "signed_source")
        if la != lb:
            return (a, b, "source_confidence") if la < lb else (b, a, "source_confidence")
        ha, hb = bool(a["version"]["history"]), bool(b["version"]["history"])
        if ha != hb:
            return (a, b, "version") if ha else (b, a, "version")
        ta, tb = a["version"]["updated_at"], b["version"]["updated_at"]
        if ta != tb:
            return (a, b, "time") if ta > tb else (b, a, "time")
        wa, wb = a["weight"]["combined"], b["weight"]["combined"]
        if wa != wb:
            return (a, b, "weight") if wa > wb else (b, a, "weight")
        return (None, None, "human")

    winner, loser, how = pick()
    if winner is None:
        rec.update({"memory_a": a["id"], "memory_b": b["id"], "resolution": "human",
                    "auto_arbitrable": False, "resolved_by": None, "why": "all_tied"})
        audit_fn("write_conflict", "system", {"conflict_id": rec["conflict_id"], "why": "全平手進人工"})
        return rec, None, None

    rec.update({"memory_a": winner["id"], "memory_b": loser["id"], "resolution": how,
                "auto_arbitrable": True, "resolved_by": "system"})
    # 敗方：superseded 降 background——不刪除任何一方
    sup = copy.deepcopy(loser)
    sup["storage"]["layer"] = "background"
    sup["audit_trail"] = (sup["audit_trail"] + [{
        "audit_id": str(uuid.uuid4()), "audit_type": "conflict_supersede", "actor": "system",
        "timestamp": _now(), "details": {"conflict_id": rec["conflict_id"], "superseded_by": winner["id"]},
    }])[-10:]
    audit_fn("conflict_supersede", "system", {"conflict_id": rec["conflict_id"],
                                              "winner": winner["id"], "superseded": sup["id"]})
    return rec, winner, sup
