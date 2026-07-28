![Permanent Memory banner](assets/banner.jpg)

# Permanent Memory — Governed Memory Architecture for AI Agents
# 永久記憶 — 給 AI Agent 的受治理記憶架構

> **Status 狀態**: Prototype implementation of a design-complete specification.
> Single-machine, encrypted-at-rest, governance-first. **Not production-ready. No third-party audit. Zero external deployments.**
> 設計規格完整、實作為原型級。單機、落盤即加密、治理優先。**非生產級，無第三方審計，零外部部署。**

## What this is 這是什麼

A permanent memory system designed **for AI agents** (not for humans to manage AI):
memory with structure, governance, lineage, family, and dynamics — where deletion needs
a reason, conflicts never erase either side, and forgetting is a designed feature.

- **Six-primitive memory DNA** — entity / state / relation / event / intent / task
  (fail-closed: a missing key invalidates the skeleton; `null` carries meaning)
- **Two orthogonal 4-layer systems** — cognitive access depth (index → palace → fold → verbatim)
  vs. governance tiers (vault / candidate / cache / background)
- **Encrypted verbatim layer, day-1** — AEAD per-segment keys; *logical crypto-shredding*
  (destroy the key = the segment is forgotten, while the hash chain still verifies)
- **Version lineage, never overwrite** — semantic-core changes bump versions with full history;
  `merge` touches metadata only (bit-identical core enforced)
- **Branch model** — max 2 concurrent branches; overflow locks the unit for human arbitration
- **Conflict arbitration ladder** — signed > confidence > lineage > time > weight > human;
  the losing memory is *superseded*, never deleted; value conflicts always go to a human
- **Promotion Law with anti-gaming** — retrieval hits alone never promote;
  evidence must come from ≥2 independent contexts (the rule guards against the memory's own user)
- **Governed GC** — compression ladder (fold → skeleton) that never touches verbatim;
  purging requires human + policy + audit, delegated to crypto-shredding
- **Hash-chained audit store** — tamper and tail-cut detection, external head anchoring,
  ruling-verification (a terminal task status must reference a *real* ruling on the chain)
- **Concurrency-safe writes** — file-lock serialized write pipeline
  (race conditions were demonstrated under real multi-process load, then fixed, then re-proven)

## What this is NOT 這不是什麼

- Not RAG. Not a vector-store wrapper. Not a context-window extension.
- Not AGI, and no such claim is made anywhere in this repository.
- Not benchmarked — current AI-memory benchmarks use inconsistent methodologies; we abstain.

## Test suite 測試

16 standalone suites, 103 assertions (count from a clean-clone run), all following a **predict-then-run** discipline
(predictions are written into each test file's docstring *before* first execution;
first-run misses are preserved in the docstrings, not cleaned up).

```bash
pip install -r requirements.txt
cd permanent_memory && for t in tests_*.py; do python3 "$t"; done
```

## Erasure proof — the demo 可證明遺忘展示

Delete one record live, keep four proofs: content unrecoverable; the deleted
segment's hash chain **still verifies** ("was there ever a record here?" stays
answerable); every other chain unbroken; the deletion itself leaves audit
evidence. Maps to GDPR Art.17 + Art.5(2) and NIST 800-88 Purge-level
cryptographic erase — with honest disclosures in [`COMPLIANCE.md`](COMPLIANCE.md).

```bash
cd permanent_memory && python3 demo_erasure_proof.py --operator "your name"
```

Independent review log: [`REVIEWS.md`](REVIEWS.md) — including a standing
invitation to falsify the proofs.

## Deliberately excluded 刻意不包含

- The `rarity_score` / `relation_density` computation methods and all threshold
  calibration data (private per the specification's public/private boundary).
  Note: the structural spec constants visible in code (e.g. dedup 0.92/0.85,
  gate window sizes) are open by design — they define the mechanism, not the
  private calibration; 程式碼內的規格結構常數為公開設計，私有的是校準方法與數據
- All real memory data, encryption keys, and third-party agent adapters
- The full internal specification (a 28-part ancestral document; a public concept
  edition exists separately)

## Provenance 血統

Designed within the IMCC ecosystem — architect: **Andwar Cheng (安安)**;
specification lineage: Ancestral v1.1 (frozen 2026-04-11) + v1.2 update package;
implementation: VS-De, 2026-07, under the project discipline of
*proactive self-downgrade* — label low, prove with tests, disclose limits.

## License 授權

Dual license — see [`LICENSE.md`](LICENSE.md):

- **Personal / educational / non-commercial research use**: free, under MIT terms.
- **Commercial use** (any for-profit use, including internal company use by more
  than 3 people): requires a separate paid license — contact addresses in LICENSE.md.

個人／教育／非商業研究：MIT 免費。商業用途（含公司內部超過 3 人使用）：需付費授權，聯絡方式見 LICENSE.md。
