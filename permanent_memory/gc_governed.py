#!/usr/bin/env python3
"""VS-9 Phase 6：GC 治理式 v0.1（祖檔 Part 5/6/7＋治理三法）
鐵律：
  - GC 作用對象=fold 摘要與壓縮狀態（沉澱物態轉換）；**永不碰 verbatim**（GC 禁區）
  - 刪 verbatim 唯一路=purge：policy 引用＋human 授權＋audit 三件齊（委派 verbatim_store.shred）
  - anchor／immutable／foundational／cache 以上層級：GC 豁免
  - 壓縮不動 dna.primitives（語義核心不因沉澱而變——Mutation Law 相容：壓縮=storage metadata 轉換）
物態階梯（Part 7）：none→folded→skeleton_only→pointer_only；skeleton 起清空 fold_summary（原文指標永留）。
閾值 [BOOTSTRAPPED]：T_FOLD=0.10／T_SKELETON=0.05——E4 校準對象，佔位不假裝已驗。
"""
import verbatim_store as vs

T_FOLD = 0.10      # [BOOTSTRAPPED] combined < T_FOLD → folded
T_SKELETON = 0.05  # [BOOTSTRAPPED] combined < T_SKELETON → skeleton_only（清 fold_summary）

LADDER = ["none", "folded", "skeleton_only", "pointer_only"]


def _exempt(u):
    return (u["memory_kind"] == "anchor" or u["foundational"]
            or u["storage"]["retention_class"] == "immutable"
            or u["storage"]["layer"] != "background")


def run_gc(memstore, actor="system"):
    """沉澱壓縮一輪。回傳 {compressed: [...], exempt: n, untouched: n}。"""
    compressed, exempt, untouched = [], 0, 0
    for u in memstore.load_all():
        if _exempt(u):
            exempt += 1
            continue
        w = u["weight"]["combined"]
        cur = u["storage"]["compression_state"]
        target = cur
        if w < T_SKELETON:
            target = "skeleton_only"
        elif w < T_FOLD:
            target = "folded"
        if LADDER.index(target) <= LADDER.index(cur):
            untouched += 1
            continue
        u["storage"]["compression_state"] = target
        if target == "skeleton_only":
            u["semantic_fold"]["fold_summary"] = {}  # 骨架化：摘要清空，primitives 與 original_ref 永留
        memstore._persist(u)
        memstore._audit("gc_compress", actor, {"unit_id": u["id"], "from": cur, "to": target,
                                               "combined_weight": w, "verbatim_untouched": True})
        compressed.append({"id": u["id"], "to": target})
    return {"compressed": compressed, "exempt": exempt, "untouched": untouched}


def purge_verbatim(memstore, segment, actor, policy_ref):
    """刪 verbatim 唯一合法路：三件齊（human＋policy＋audit）→ 委派 crypto-shred。"""
    if actor != "human":
        memstore._audit("bap_reject", actor, {"op": "purge_verbatim", "segment": segment,
                                              "why": "GC 禁區：verbatim 刪除需 human"})
        raise PermissionError("purge 需 human actor（bap_reject 已記）")
    if not policy_ref:
        raise ValueError("purge 需明示 policy_ref（三件齊之一）")
    rec = memstore._audit("purge_policy_invoked", actor, {"segment": segment, "policy_ref": policy_ref})
    result = vs.shred(segment, actor=actor, reason=f"purge policy {policy_ref}（audit {rec['audit_id']}）")
    return {"purge_audit": rec["audit_id"], "shred": result}
