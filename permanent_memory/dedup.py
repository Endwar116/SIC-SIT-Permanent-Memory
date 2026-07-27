#!/usr/bin/env python3
"""VS-9 Phase 5：Dedup 三分法 v0.1（祖檔 Part 16＋v1.2 P-3）
  score > 0.92 且 same_causal_identity → MERGE（只動 metadata，mutation.merge）
  score > 0.85 且應演化               → VERSION_UPDATE（升版，血統保留）
  其餘                                → WRITE_NEW
P-3 鐵律：**不同 task.id 的相似信號不是重複，是平行** → WRITE_NEW（不跨任務去重）。
[BOOTSTRAPPED]：相似度 v1 = difflib 序列比對於六原語正規化序列化——非語義相似度；
  E1 之後可換 embedding。0.92/0.85 是 Part 16 規格常數（非 Phase 3 未定閾值），照抄。
"""
import difflib
import json

MERGE_THRESHOLD = 0.92    # Part 16 [FROZEN in spec]
VERSION_THRESHOLD = 0.85  # Part 16 [FROZEN in spec]


def _serial(unit: dict) -> str:
    return json.dumps(unit["dna"]["primitives"], ensure_ascii=False, sort_keys=True)


def similarity(a: dict, b: dict) -> float:
    """[BOOTSTRAPPED] 序列比對相似度（0-1）。"""
    return difflib.SequenceMatcher(None, _serial(a), _serial(b)).ratio()


def same_causal_identity(a: dict, b: dict) -> bool:
    """因果同一性：causal_chain 相同非空，或 task(id+deliverable) 相同（P-3：deliverable=dedup 錨點）。"""
    ca, cb = a["dna"]["causal_chain"], b["dna"]["causal_chain"]
    if ca and ca == cb:
        return True
    ta, tb = a["dna"]["primitives"]["task"], b["dna"]["primitives"]["task"]
    if ta and tb and ta["id"] == tb["id"] and ta["deliverable"] == tb["deliverable"]:
        return True
    return False


def decide(new_unit: dict, existing_units: list[dict]) -> dict:
    """對庫決策。回傳 {action, target_id|None, score|None}。"""
    best, best_score = None, 0.0
    new_owner = new_unit.get("provenance", {}).get("owner")
    for ex in existing_units:
        # F34 修（R234）：不同 owner 的相似記憶=平行非重複（P-3 的 owner 版）——
        # 否則不同 agent 的相似記憶會被互相 MERGE/升版。
        if new_owner and ex.get("provenance", {}).get("owner") != new_owner:
            continue
        # P-3：不同 task.id = 平行信號，不參與去重比對
        tn, te = new_unit["dna"]["primitives"]["task"], ex["dna"]["primitives"]["task"]
        if tn and te and tn["id"] != te["id"]:
            continue
        s = similarity(new_unit, ex)
        if s > best_score:
            best, best_score = ex, s

    if best is None or best_score <= VERSION_THRESHOLD:
        return {"action": "WRITE_NEW", "target_id": None, "score": round(best_score, 4)}
    # should_version_update 正式規格（原設計者 2026-07-25 正式化，補祖檔 Part 16 缺口）：
    # := NOT deep_equal(primitives)。第一原則=零丟失優先於去重（升版可回收、MERGE丟資訊不可回收）。
    # （R225 我的補位裁量與此定義一致，Q14 已由設計者正式化。）
    core_identical = _serial(new_unit) == _serial(best) and         new_unit["dna"]["causal_chain"] == best["dna"]["causal_chain"]
    if best_score > MERGE_THRESHOLD and same_causal_identity(new_unit, best) and core_identical:
        return {"action": "MERGE", "target_id": best["id"], "score": round(best_score, 4)}
    return {"action": "VERSION_UPDATE", "target_id": best["id"], "score": round(best_score, 4)}
