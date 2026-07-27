#!/usr/bin/env python3
"""VS-9：Memory Store v0.1（單元落盤層——Storage Contract 六 MUST 的真落點）
選型：純檔案系統＋JSON（收斂期不引新依賴；Part 18 初版建議「最輕量選項先跑通」）。
  M-1 append-only：verbatim（verbatim_store）＋audit（本層 audit.jsonl）皆 append-only
  M-2 原子寫入：tmp 檔＋os.replace（POSIX 原子換名）——函數級鎖（F10）在此升級為檔案級
  M-3 audit hook：每次寫入必寫 audit 行
  M-4 簽名等效存放：integrity_signature 內嵌單元檔，同持久等級
  M-5 三軸可查：entity / task.id / time range（query()）
  M-6 retention 可執行：immutable 單元在 store 層拒改（BAP 路線）
單元檔會被升版覆蓋（版本史在單元內 version.history 保存）——「覆寫檔案」≠「覆寫記憶」，
血統完整；真正 append-only 的是 verbatim 與 audit 兩本帳。
"""
import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import dedup
import mutation
import pm_validate
from audit_chain import ChainedAudit


class BAPReject(PermissionError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self, root):
        self.root = Path(root)
        self.units_dir = self.root / "units"
        self.units_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = self.root / "audit.jsonl"
        self.audit = ChainedAudit(self.audit_path)  # R240：audit 上鏈（F4 根治）

    # ── audit（M-1/M-3；R240 起=hash 鏈式）──
    def _audit(self, audit_type, actor, details):
        return self.audit.append(audit_type, actor, details)

    # ── 原子落盤（M-2）──
    def _persist(self, unit):
        target = self.units_dir / f"{unit['id']}.json"
        tmp = target.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(unit, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)  # POSIX 原子換名
        return target

    def load_all(self):
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.units_dir.glob("*.json"))]

    def get(self, unit_id):
        p = self.units_dir / f"{unit_id}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    # ── 寫入管線（Part 16 下半場：dedup→衝突位→寫）──
    def write(self, new_unit, actor="system"):
        # R248（F41 修）：load_all→dedup.decide→persist 是跨檔 read-modify-write——
        # store 級寫鎖序列化整個寫入管線（真併發實證：無鎖時 dedup 讀到彼此的中間態）
        lockf = open(self.root / "store.lock", "w")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            return self._write_locked(new_unit, actor)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()

    def _write_locked(self, new_unit, actor="system"):
        v = pm_validate.validate_unit(new_unit, ruling_exists=self.audit.exists)
        if v["status"] == "FAIL":
            self._audit("write_rejected", actor, {"why": "validator FAIL", "errors": v["errors"][:3],
                                                  "unit_id": new_unit.get("id")})
            return {"action": "REJECTED", "validator": v}

        existing = self.load_all()
        decision = dedup.decide(new_unit, existing)

        if decision["action"] == "WRITE_NEW":
            if self.get(new_unit["id"]) is not None:  # F37 修（R234）：id 撞號=靜默覆蓋風險，拒收
                self._audit("write_rejected", actor, {"why": "id collision", "unit_id": new_unit["id"]})
                return {"action": "REJECTED", "why": f"id {new_unit['id']} 已存在（WRITE_NEW 不覆蓋；演化走 VERSION_UPDATE）"}
            self._persist(new_unit)
            self._audit("unit_written", actor, {"unit_id": new_unit["id"], "layer": new_unit["storage"]["layer"]})
            return {"action": "WRITE_NEW", "unit_id": new_unit["id"]}

        target = self.get(decision["target_id"])

        if decision["action"] == "MERGE":
            merged = mutation.merge(target, weight_dynamic_value=min(
                1.0, target["weight"]["dynamic"]["value"] + 0.05))
            self._persist(merged)
            self._audit("unit_merged", actor, {"target": target["id"], "duplicate_of": new_unit["id"],
                                               "note": "重複信號：metadata 微調，結構不生成（原文已在 verbatim）"})
            return {"action": "MERGE", "unit_id": target["id"]}

        # VERSION_UPDATE：immutable 在 store 層拒（M-6/BAP）
        if target["storage"]["retention_class"] == "immutable":
            self._audit("bap_reject", actor, {"op": "version_update", "target": target["id"],
                                              "why": "immutable 單元 store 層拒改"})
            raise BAPReject(f"unit {target['id']} 為 immutable，拒絕演化寫入（audit 已記）")

        evolved = mutation.version_update(
            target,
            new_primitives=new_unit["dna"]["primitives"],
            new_causal_chain=new_unit["dna"]["causal_chain"],
            change_summary=f"dedup VERSION_UPDATE（score={decision['score']}，來源單元 {new_unit['id']}）",
            actor=actor,
        )
        self._persist(evolved)
        self._audit("unit_evolved", actor, {"target": target["id"], "new_version": evolved["version"]["current_number"]})
        return {"action": "VERSION_UPDATE", "unit_id": target["id"],
                "version": evolved["version"]["current_number"]}

    # ── 三軸可查（M-5）──
    def query(self, entity_id=None, task_id=None, since=None, until=None):
        out = []
        for u in self.load_all():
            if entity_id and entity_id not in {e["id"] for e in u["dna"]["primitives"]["entity"]}:
                continue
            t = u["dna"]["primitives"]["task"]
            if task_id and (t is None or t["id"] != task_id):
                continue
            ts = u["version"]["updated_at"]
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            out.append(u)
        return out
