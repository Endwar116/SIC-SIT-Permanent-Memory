#!/usr/bin/env python3
"""VS-9 Phase 2：版本鏈＋Mutation Law v0.1
規格依據：祖檔 Part 13（Mutation Law）＋Part 15 version 結構＋v1.2 P-2 治理鉤子＋P-15.4 詞彙鎖定。
鐵則：
  - merge 只動 metadata（weight / audit_trail / updated_at），永不動 semantic core，不升版
  - semantic core（dna.primitives / dna.causal_chain）任何改變 = 升版＋history 快照。「記憶重寫」=VERSION_UPDATE，不存在覆寫
  - task.status 變更 = 語義核心變動（P-2 鉤子1）；終態需先取得裁定 audit_id（R-2 寫入順序：裁定先入外部 store，記憶後寫）
  - immutable 記憶的 semantic core 不可動（BAP 路線，此處直接拒絕）
"""
import copy
import json
from datetime import datetime, timezone

TERMINAL = {"completed", "dismissed", "archived"}


class MutationLawError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _core(u):
    return {"primitives": u["dna"]["primitives"], "causal_chain": u["dna"]["causal_chain"]}


def merge(unit: dict, weight_dynamic_value: float | None = None, audit_entry: dict | None = None) -> dict:
    """metadata 級合併：不升版。嘗試經 merge 改核心=呼叫端錯誤，本函數根本不接收核心參數（介面級防呆）。"""
    u = copy.deepcopy(unit)
    before_core = json.dumps(_core(u), ensure_ascii=False, sort_keys=True)
    if weight_dynamic_value is not None:
        u["weight"]["dynamic"]["value"] = weight_dynamic_value
        u["weight"]["dynamic"]["last_adjusted_at"] = _now()
        u["weight"]["combined"] = u["weight"]["fixed"]["value"] + weight_dynamic_value
    if audit_entry is not None:
        u["audit_trail"] = (u["audit_trail"] + [audit_entry])[-10:]
    u["version"]["updated_at"] = _now()
    # 自我驗證：merge 前後 core 必須逐位元相同（防呆的防呆）
    if json.dumps(_core(u), ensure_ascii=False, sort_keys=True) != before_core:
        raise MutationLawError("merge 改動了 semantic core——Mutation Law 違規")
    return u


def version_update(unit: dict, new_primitives: dict | None = None, new_causal_chain: list | None = None,
                   change_summary: str = "", actor: str = "system",
                   ruling_audit_id: str | None = None) -> dict:
    """semantic core 變更：升版＋快照。終態 task 需 ruling_audit_id（R-2）。"""
    if unit["storage"]["retention_class"] == "immutable":
        raise MutationLawError("immutable 記憶的 semantic core 不可變（解封走 human+audit 特殊流程，非本 API）")
    if unit["version"].get("locked"):
        raise MutationLawError("branch_overflow 鎖定中：semantic core 寫入停止，僅允許 metadata append（等人工仲裁）")
    if not change_summary:
        raise MutationLawError("version_update 必須附 change_summary（血統可讀性）")

    # F6 修（R220）：no-op 拒升——核心無變化不得灌版本
    probe = copy.deepcopy(unit["dna"]["primitives"])
    if new_primitives is not None:
        probe = {**probe, **new_primitives}
    new_cc = new_causal_chain if new_causal_chain is not None else unit["dna"]["causal_chain"]
    if json.dumps({"p": probe, "c": new_cc}, ensure_ascii=False, sort_keys=True) == \
       json.dumps({"p": unit["dna"]["primitives"], "c": unit["dna"]["causal_chain"]}, ensure_ascii=False, sort_keys=True):
        raise MutationLawError("no-op：semantic core 無變化，拒絕升版（防版本鏈通膨）")

    u = copy.deepcopy(unit)
    old_task = u["dna"]["primitives"]["task"]
    new_task = (new_primitives or {}).get("task", old_task)

    # P-2 鉤子：task.status 轉終態 → 裁定先行
    if new_task is not None and new_task.get("status") in TERMINAL:
        if old_task is None or old_task.get("status") != new_task["status"]:
            if not ruling_audit_id:
                raise MutationLawError(
                    f"task.status→{new_task.get('status')} 為終態：需先在外部 audit store 取得裁定 audit_id（R-2 寫入順序）")
            u["audit_trail"] = (u["audit_trail"] + [{
                "audit_id": ruling_audit_id, "audit_type": "task_terminal_ruling",
                "actor": actor, "timestamp": _now(),
                "details": {"ruling_audit_id": ruling_audit_id, "to_status": new_task["status"]},
            }])[-10:]

    # history 快照（舊核心入鏈，血統保留）
    u["version"]["history"] = u["version"]["history"] + [{
        "version_number": u["version"]["current_number"],
        "label": u["version"]["current_label"],
        "snapshot_ref": None,
        "core_snapshot": _core(unit),
        "changed_at": _now(),
        "change_summary": change_summary,
    }]
    u["version"]["current_number"] += 1
    u["version"]["current_label"] = f"v{u['version']['current_number']}"
    u["version"]["updated_at"] = _now()

    if new_primitives is not None:
        u["dna"]["primitives"] = {**u["dna"]["primitives"], **new_primitives}
    if new_causal_chain is not None:
        u["dna"]["causal_chain"] = new_causal_chain
    return u


# ── Part 19 樂觀鎖 + Part 14 Branch Model（R220，Phase 2 收尾）──────────────

MAX_BRANCHES = 2  # [FROZEN] Part 14


def write_with_lock(unit: dict, expected_version: int, operation: str, actor: str,
                    audit_fn, **kwargs) -> dict:
    """樂觀鎖寫入。audit_fn(audit_type, actor, details) 為外部 audit store 介面（Audit Law 事件不落單元內）。
    回傳 {"status": ..., "unit": ...}；status ∈ committed / committed_after_retry / conflict_flagged / overflow_locked
    """
    current = unit["version"]["current_number"]

    if current == expected_version:
        if operation == "merge":
            return {"status": "committed", "unit": merge(unit, **kwargs)}
        if operation == "version_update":
            return {"status": "committed", "unit": version_update(unit, actor=actor, **kwargs)}
        raise MutationLawError(f"未知操作 {operation}")

    # ── 版本已被別的 instance 動過：衝突路徑 ──
    if operation == "merge":
        # merge 只動 metadata，對新版本重放是安全的（Part 19：retry）
        audit_fn("write_conflict", actor, {"op": "merge", "expected": expected_version, "actual": current, "resolution": "retry"})
        return {"status": "committed_after_retry", "unit": merge(unit, **kwargs)}

    if operation == "version_update":
        u = copy.deepcopy(unit)
        branches = u["version"].get("branches", [])
        branch = {
            "branch_id": f"branch-{len(branches) + 1}",
            "base_version": expected_version,
            "actor": actor,
            "created_at": _now(),
            "proposed": {"new_primitives": kwargs.get("new_primitives"),
                          "new_causal_chain": kwargs.get("new_causal_chain"),
                          "change_summary": kwargs.get("change_summary", "")},
        }
        branches = branches + [branch]
        u["version"]["branches"] = branches
        audit_fn("branch_created", actor, {"branch_id": branch["branch_id"], "base_version": expected_version})

        if len(branches) > MAX_BRANCHES:  # Part 14 overflow fallback
            u["version"]["locked"] = True
            audit_fn("branch_overflow", actor, {"branch_count": len(branches), "action": "semantic 寫入停止，進 arbitration_queue"})
            return {"status": "overflow_locked", "unit": u}
        return {"status": "conflict_flagged", "unit": u}

    raise MutationLawError(f"未知操作 {operation}")


# ── 分支合併/仲裁路徑（R221，修紅隊 F9；F12 的 R-2 重檢在 version_update 內天然發生）──

def resolve_branches(unit: dict, winner_branch_id: str, actor: str, audit_fn,
                     ruling_audit_id: str | None = None) -> dict:
    """人工仲裁合併：套用勝方分支提案（走 version_update 全檢），敗方留 audit，解鎖。
    Part 14：branch_overflow 等人工裁定合併至少一個分支；BAP：仲裁鎖定狀態下只有 human 可解。"""
    branches = unit["version"].get("branches", [])
    if not branches:
        raise MutationLawError("無分支可仲裁")
    if unit["version"].get("locked") and actor != "human":
        audit_fn("bap_reject", actor, {"op": "resolve_branches", "why": "overflow 鎖定下僅 human 可仲裁"})
        raise MutationLawError("overflow 鎖定：僅 human 可仲裁（bap_reject 已記）")
    winner = next((b for b in branches if b["branch_id"] == winner_branch_id), None)
    if winner is None:
        raise MutationLawError(f"分支 {winner_branch_id} 不存在")

    losers = [b["branch_id"] for b in branches if b["branch_id"] != winner_branch_id]

    # 解鎖後套用勝方提案——version_update 全檢重跑（immutable/no-op/R-2 終態裁定：F12 防漏點）
    u = copy.deepcopy(unit)
    u["version"]["locked"] = False
    u = version_update(
        u,
        new_primitives=winner["proposed"].get("new_primitives"),
        new_causal_chain=winner["proposed"].get("new_causal_chain"),
        change_summary=f"branch_merged: {winner_branch_id} 勝出（{winner['proposed'].get('change_summary','')}）",
        actor=actor,
        ruling_audit_id=ruling_audit_id,
    )
    u["version"]["branches"] = []
    audit_fn("branch_merged", actor, {"winner": winner_branch_id, "losers_superseded": losers,
                                      "loser_proposals_preserved_in": "this audit record",
                                      "loser_proposals": [b["proposed"] for b in branches if b["branch_id"] != winner_branch_id]})
    return u
