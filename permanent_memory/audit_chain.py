#!/usr/bin/env python3
"""VS-9 Phase 6：鏈式 Audit Store v0.1（Audit Law 的「外部 append-only store」真身）
根治：F4（audit.jsonl 裸帳）＋F7（merge 注入假 task_terminal_ruling 騙過 validator）。
鏈法同 verbatim：chain_hash = sha256(prev + sha256(record_core))；頭可外錨防砍尾。
R-2 寫入順序的全流程從此可執行：裁定先 append 取真 audit_id → 記憶單元後寫 → validator 回查存在性。
"""
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _now():
    return datetime.now(timezone.utc).isoformat()


class ChainedAudit:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _tail(self):
        if not self.path.exists():
            return GENESIS
        last = None
        for line in open(self.path, encoding="utf-8"):
            if line.strip():
                last = json.loads(line)
        return last["chain_hash"] if last else GENESIS

    def append(self, audit_type, actor, details):
        core = {"audit_id": str(uuid.uuid4()), "audit_type": audit_type,
                "actor": actor, "timestamp": _now(), "details": details}
        core_hash = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        # R248（F40 修）：read-tail→append 是 read-modify-write，必須在同一把檔案鎖內——
        # 真併發壓測實證無鎖會斷鏈（4行程×10筆，鏈在第1筆分叉）
        lockf = open(self.path.with_suffix(".lock"), "w")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            prev = self._tail()
            rec = {**core, "core_hash": core_hash, "prev_hash": prev,
                   "chain_hash": hashlib.sha256((prev + core_hash).encode()).hexdigest()}
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
            lockf.close()
        return rec

    def verify(self):
        prev, n = GENESIS, 0
        for line in open(self.path, encoding="utf-8"):
            rec = json.loads(line)
            core = {k: rec[k] for k in ("audit_id", "audit_type", "actor", "timestamp", "details")}
            ch = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if ch != rec["core_hash"] or rec["prev_hash"] != prev or \
               rec["chain_hash"] != hashlib.sha256((prev + ch).encode()).hexdigest():
                return {"ok": False, "at": n}
            prev, n = rec["chain_hash"], n + 1
        return {"ok": True, "entries": n, "head": prev}

    def checkpoint_head(self):
        v = self.verify()
        if not v["ok"]:
            raise RuntimeError(f"鏈已壞拒絕外錨：{v}")
        cp = self.path.with_suffix(".head.json")
        tmp = cp.with_suffix(".tmp")
        json.dump({"head": v["head"], "entries": v["entries"], "at": _now()},
                  open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, cp)
        return v

    def verify_against_head(self):
        cp = self.path.with_suffix(".head.json")
        if not cp.exists():
            return {"ok": None, "why": "無外錨"}
        anchor = json.load(open(cp, encoding="utf-8"))
        heads, prev = [], GENESIS
        for line in open(self.path, encoding="utf-8"):
            heads.append(json.loads(line)["chain_hash"])
        if len(heads) < anchor["entries"] or heads[anchor["entries"] - 1] != anchor["head"]:
            return {"ok": False, "why": "尾切或改寫（外錨不符）"}
        return self.verify()

    def exists(self, audit_id):
        """R-2 回查：裁定 audit_id 是否真的在鏈上（F7 根治的查詢面）。"""
        if not self.path.exists():
            return False
        for line in open(self.path, encoding="utf-8"):
            if json.loads(line)["audit_id"] == audit_id:
                return True
        return False
