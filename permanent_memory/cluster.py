#!/usr/bin/env python3
"""VS-9：記憶叢 v1（增補 A P-15，R-10 已裁）
叢 = 共享至少一個顯式鍵的記憶集合。顯式鍵（v1）：task.id ｜ entity.id ｜ causal_chain 交集。
**禁止** relation_density 自動聚類（v2，等 E1）——用 UNDEFINED 閾值定義核心概念=把叢押在 blocker 上。
血統（縱向）=version chain；家族（橫向）=cluster。一條記憶：一條血統、零到多個家族。
叢級聯動寫入四步（P-15.3）：①叢內 dedup 優先 ②叢權重連動 ③叢內衝突優先檢測 ④叢索引更新。
"""
import json
from pathlib import Path

import conflict
import dedup
import mutation

CLUSTER_ACTIVITY_BUMP = 0.02  # [BOOTSTRAPPED] 叢活躍度信號量，E4 期一併校準


def explicit_keys(unit):
    keys = set()
    t = unit["dna"]["primitives"]["task"]
    if t:
        keys.add(f"task:{t['id']}")
    for e in unit["dna"]["primitives"]["entity"]:
        keys.add(f"entity:{e['id']}")
    for c in unit["dna"]["causal_chain"]:
        keys.add(f"chain:{c}")
    return keys


def build_clusters(units):
    """key → [unit_id…]（宮殿房間成員名單的資料源）。"""
    fam = {}
    for u in units:
        for k in explicit_keys(u):
            fam.setdefault(k, []).append(u["id"])
    return fam


def cluster_of(unit, units):
    """與 unit 共享 ≥1 顯式鍵的其他單元（同 owner——家族不跨資料主權）。"""
    mine = explicit_keys(unit)
    owner = unit.get("provenance", {}).get("owner")
    return [u for u in units
            if u["id"] != unit["id"]
            and u.get("provenance", {}).get("owner") == owner
            and explicit_keys(u) & mine]


def cluster_aware_write(memstore, new_unit, actor="system"):
    """P-15.3 四步聯動。回傳 {store_result, family_size, weight_bumped, conflicts, index_path}。"""
    all_units = memstore.load_all()
    family = cluster_of(new_unit, all_units)

    # ① 叢內 dedup 優先：先對家族比對；家族內無定論才全庫（dedup 本身已 owner 分區）
    fam_decision = dedup.decide(new_unit, family) if family else {"action": "WRITE_NEW"}
    if fam_decision["action"] != "WRITE_NEW":
        result = memstore.write(new_unit, actor=actor)  # store.write 重跑 decide 會得同一目標（家族⊆全庫）
    else:
        result = memstore.write(new_unit, actor=actor)

    # ② 叢權重連動（新成員入家族=活躍度信號；只在真的新增/演化時）
    bumped = 0
    if result["action"] in ("WRITE_NEW", "VERSION_UPDATE"):
        for m in family:
            cur = memstore.get(m["id"])  # R239 修：重取最新版——用寫入前快照落盤=把剛升版的成員蓋回舊版（CL6 抓到）
            if cur is None or cur["storage"]["retention_class"] == "immutable":
                continue
            nu = mutation.merge(cur, weight_dynamic_value=min(1.0, cur["weight"]["dynamic"]["value"] + CLUSTER_ACTIVITY_BUMP))
            memstore._persist(nu)
            bumped += 1

    # ③ 叢內衝突優先檢測（近親最可能矛盾）——只報告，仲裁另走 conflict.arbitrate
    conflicts = [m["id"] for m in family if conflict.detect_conflict(new_unit, m)]

    # ④ 叢索引更新（宮殿房間成員名單）
    idx = build_clusters(memstore.load_all())
    idx_path = Path(memstore.root) / "cluster_index.json"
    tmp = idx_path.with_suffix(".json.tmp")
    json.dump({k: v for k, v in sorted(idx.items())}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import os
    os.replace(tmp, idx_path)

    return {"store_result": result, "family_size": len(family), "weight_bumped": bumped,
            "conflicts_in_family": conflicts, "index_path": str(idx_path)}
