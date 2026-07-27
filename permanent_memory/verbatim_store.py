#!/usr/bin/env python3
"""VS-9 Phase 1：加密 verbatim 段檔庫 v0.1（R-12 day-1 encrypted-at-rest）
規格依據：部署包 §3.1（裁定=紅隊審查報告 2026-07-24，採外部設計審查方案+補論證）
  - AEAD（ChaCha20-Poly1305）逐條加密；分段金鑰（v1 粒度=YYYY-MM，紅隊報告建議2）
  - hash 鏈對「密文」計算（紅隊報告核心論證：shred 後密文仍在、鏈仍可驗=T12）
  - shred=金鑰檔就地零覆寫（相容 AGR 不硬刪鐵律：檔案留存、內容不可復原）
  - 銷鑰=Audit Law 事件雙寫 delete_attempt+retention_change（紅隊報告建議3）
[BOOTSTRAPPED]：SSD 物理層 secure-erase 未處理（wear-leveling 殘影）；key registry 單點風險=O-3（備援未設計，紅隊報告建議4）。
"""
import base64
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

DATA = Path(__file__).parent / "data"
SEGS = DATA / "verbatim"
KEYS = DATA / "keys"
AUDIT = DATA / "audit.jsonl"
REGISTRY = KEYS / "keys_registry.json"

GENESIS = "0" * 64


class SegmentShredded(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _registry():
    if REGISTRY.exists():
        return json.load(open(REGISTRY, encoding="utf-8"))
    return {}


def _save_registry(reg):
    KEYS.mkdir(parents=True, exist_ok=True)
    json.dump(reg, open(REGISTRY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _audit(audit_type, actor, details):
    DATA.mkdir(parents=True, exist_ok=True)
    rec = {"audit_id": str(uuid.uuid4()), "audit_type": audit_type, "actor": actor,
           "timestamp": _now(), "details": details}
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _key_for(segment, create=False):
    reg = _registry()
    meta = reg.get(segment)
    kf = KEYS / f"{segment}.key"
    if meta and meta["status"] == "shredded":
        raise SegmentShredded(f"segment {segment} 已銷鑰（{meta['shredded_at']}）")
    if meta is None:
        if not create:
            raise KeyError(f"segment {segment} 不存在")
        KEYS.mkdir(parents=True, exist_ok=True)
        key = ChaCha20Poly1305.generate_key()
        kf.write_bytes(key)
        os.chmod(kf, 0o600)
        reg[segment] = {"created_at": _now(), "status": "active"}
        _save_registry(reg)
        return key
    return kf.read_bytes()


def _seg_file(segment):
    SEGS.mkdir(parents=True, exist_ok=True)
    return SEGS / f"{segment}.jsonl"


def _tail_chain(segment):
    f = _seg_file(segment)
    if not f.exists():
        return 0, GENESIS
    last = None
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = json.loads(line)
    return (last["seq"] + 1, last["chain_hash"]) if last else (0, GENESIS)


def append(text: str, ts: str | None = None, segment: str | None = None) -> dict:
    """原料全收（R-7：Gate 擋結構生成，不擋原料保存）。回傳定位 {segment, seq, ct_sha256}。"""
    ts = ts or _now()
    segment = segment or ts[:7]  # YYYY-MM
    key = _key_for(segment, create=True)
    nonce = secrets.token_bytes(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, text.encode("utf-8"), segment.encode())
    ct_hash = hashlib.sha256(ct).hexdigest()
    seq, prev = _tail_chain(segment)
    chain_hash = hashlib.sha256((prev + ct_hash).encode()).hexdigest()
    rec = {"seq": seq, "ts": ts, "nonce": base64.b64encode(nonce).decode(),
           "ct": base64.b64encode(ct).decode(), "ct_sha256": ct_hash,
           "prev_hash": prev, "chain_hash": chain_hash}
    with open(_seg_file(segment), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return {"segment": segment, "seq": seq, "ct_sha256": ct_hash}


def read(segment: str, seq: int) -> str:
    key = _key_for(segment)
    with open(_seg_file(segment), encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["seq"] == seq:
                return ChaCha20Poly1305(key).decrypt(
                    base64.b64decode(rec["nonce"]), base64.b64decode(rec["ct"]), segment.encode()
                ).decode("utf-8")
    raise KeyError(f"{segment}:{seq} 不存在")


def verify_chain(segment: str) -> dict:
    """只用密文驗鏈——不需要金鑰，shred 後仍可驗（T12 核心性質）。"""
    prev, n = GENESIS, 0
    with open(_seg_file(segment), encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            ct_hash = hashlib.sha256(base64.b64decode(rec["ct"])).hexdigest()
            if ct_hash != rec["ct_sha256"]:
                return {"ok": False, "at": rec["seq"], "why": "ct hash mismatch"}
            expect = hashlib.sha256((prev + ct_hash).encode()).hexdigest()
            if expect != rec["chain_hash"] or rec["prev_hash"] != prev:
                return {"ok": False, "at": rec["seq"], "why": "chain broken"}
            prev, n = rec["chain_hash"], n + 1
    return {"ok": True, "entries": n, "head": prev}


def checkpoint(segment: str, actor: str = "system") -> dict:
    """鏈頭外錨（紅隊 F2 過渡方案；正解=Phase 3 Merkle checkpoint）。
    把段鏈當前 head+entries 寫進 audit 鏈——此後砍尾可被 verify_against_checkpoint 偵測。"""
    v = verify_chain(segment)
    if not v["ok"]:
        raise RuntimeError(f"鏈本身已壞，拒絕 checkpoint：{v}")
    return _audit("chain_checkpoint", actor, {"segment": segment, "head": v["head"], "entries": v["entries"]})


def verify_against_checkpoint(segment: str) -> dict:
    """對最後一個外錨驗證：抓 verify_chain 抓不到的「砍尾」（append-only 違規）。"""
    cp = None
    if AUDIT.exists():
        for line in open(AUDIT, encoding="utf-8"):
            rec = json.loads(line)
            if rec["audit_type"] == "chain_checkpoint" and rec["details"]["segment"] == segment:
                cp = rec["details"]
    if cp is None:
        return {"ok": None, "why": "無 checkpoint 可對"}
    heads, prev = [], GENESIS
    with open(_seg_file(segment), encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            heads.append(rec["chain_hash"])
    if len(heads) < cp["entries"] or heads[cp["entries"] - 1] != cp["head"]:
        return {"ok": False, "why": f"尾切或改寫：checkpoint 記 entries={cp['entries']} head={cp['head'][:12]}…，現況不符"}
    chain = verify_chain(segment)
    return {"ok": chain["ok"], "entries_now": len(heads), "checkpoint_entries": cp["entries"]}


def shred(segment: str, actor: str, reason: str) -> dict:
    """被遺忘權（R-12）：金鑰就地零覆寫。需 human actor（purge policy＋人工授權＋audit 三件齊）。"""
    if actor != "human":
        rec = _audit("bap_reject", actor, {"op": "shred", "segment": segment,
                                           "why": "verbatim 刪除需人工授權（GC 禁區）"})
        raise PermissionError(f"shred 需 human actor，已寫 bap_reject audit {rec['audit_id']}")
    reg = _registry()
    if segment not in reg:
        raise KeyError(f"segment {segment} 不存在")
    if reg[segment]["status"] == "shredded":
        return reg[segment]
    kf = KEYS / f"{segment}.key"
    size = kf.stat().st_size
    with open(kf, "r+b") as f:  # 就地零覆寫（AGR 相容：不 rm，內容不可復原）
        f.write(b"\x00" * size)
        f.flush()
        os.fsync(f.fileno())
    a1 = _audit("delete_attempt", actor, {"op": "crypto_shred", "segment": segment, "reason": reason, "result": "key_zeroized"})
    a2 = _audit("retention_change", actor, {"segment": segment, "from": "active", "to": "shredded", "ruling_ref": a1["audit_id"]})
    reg[segment] = {**reg[segment], "status": "shredded", "shredded_at": _now(), "audit": [a1["audit_id"], a2["audit_id"]]}
    _save_registry(reg)
    return reg[segment]
