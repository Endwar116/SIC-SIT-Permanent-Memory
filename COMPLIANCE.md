# Compliance Mapping 合規對照（self-assessment 自我聲明）

> **This is a self-assessment, not a third-party audit.** Every claim below is
> reproducible from a clean clone; run the referenced tests/demos yourself.
> 本文件為自我聲明，非第三方稽核。每條主張都可從乾淨 clone 重現，請自行驗證。

## GDPR mapping

| Requirement | What this system does | Evidence (run it) |
|---|---|---|
| **Art. 17** Right to erasure | Per-segment cryptographic erasure: key zeroized in place; content becomes unrecoverable | `demo_erasure_proof.py` proof 1 |
| **Art. 5(2)** Accountability | Deletion itself is evidenced: double audit event (delete_attempt + retention_change), hash-chained | `demo_erasure_proof.py` proof 4 |
| Art. 17 + 5(2) combined | "Delete it AND prove you did" — after erasure the hash chain still verifies, so *"did a record ever exist here?"* remains answerable without exposing content | proofs 2 + 3 |

## NIST SP 800-88 alignment

Cryptographic Erase is listed as a **Purge-level** sanitization technique.
This system implements CE for its encrypted-at-rest record store (per-segment
ChaCha20-Poly1305 keys; shred = in-place key zeroization + audit).

## Honest disclosures 誠實揭露（read before relying on any of the above）

1. **Cryptographic erasure, not physical media sanitization.** Ciphertext
   remains on disk (this is what keeps the audit chain verifiable). Regulators
   and auditors differ on whether key destruction constitutes legal deletion —
   the law asks that data *not exist*, not that nobody can read it. A dual-track
   design (key destruction first, scheduled physical clearing of ciphertext
   second) is planned, **not yet implemented**.
   本系統採用金鑰銷毀而非物理抹除；「毀鑰=刪除」的稽核接受度不一，雙軌第二軌（排程物理清除密文）未實作。
2. **Data at rest only.** While a process runs, decrypted content is plaintext
   in RAM. This does not defend a live memory dump of the machine.
3. **Deletion-verification discipline**: space reclamation and content
   unfindability are verified as *separate* criteria (single-row byte checks
   can pass spuriously when rows share a page; batch multi-page deletion is
   the meaningful space test).
4. **No third-party audit yet.** Independent review status: see `REVIEWS.md`.
5. SSD wear-leveling residuals of zeroized key files are out of scope
   (documented limitation since v0.1).

*Self-assessment first published 2026-07-28. Corrections welcome — file an issue.*
