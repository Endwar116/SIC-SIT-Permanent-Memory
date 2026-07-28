# Independent Review Log 獨立審查紀錄

> Reviewer identities are withheld pending their consent and are available from
> the project owner. What matters here is **what was done and whether you can
> reproduce it** — every reviewed claim is re-runnable from this repo.
> 審查者身分候本人同意後公開（可向專案擁有者索取）；重點是審了什麼、你能否重現。

| Date | Reviewer | Scope & method | Result |
|---|---|---|---|
| 2026-07-25 | Reviewer A — independent AI system, **different machine/vendor** from the implementer | Unzipped the package in its own container, installed deps, ran the full test suite from a clean copy; separately audited git-tracked files for key/PII leakage across full history | 16/16 suites pass, 103 assertions; 0 keys tracked in git across all history; flagged a real packaging risk (working-directory zips carry live keys) which is now a hard rule |
| 2026-07-27 | Reviewer A (follow-up) | Deep pre-publication verification from a simulated cloner's perspective, incl. git history archaeology | Found 3 must-fix issues (stale license pointer; over-claimed test count 130+ vs measured 103; internal doc recoverable from git history). All three fixed; history rebuilt to a single clean commit **before** first push |
| 2026-07-28 | Reviewer B — external AI advisor (outside this project's ecosystem) | Design review of deletion governance and vector-layer plans | Contributed three adopted findings: tombstone-style fake deletion (space must be *measured*, not assumed — now `tests_purge.py`); vector inversion risk (vectors never leave home + encrypted at rest); score reporting must state sample size (calibration bank started, baseline n=16) |

## Standing invitation 常設邀請

Try to falsify the erasure proofs: recover deleted content, or break a
surviving segment's chain, using only what this repo provides
(`demo_erasure_proof.py`). Write-ups of successful *or failed* attempts are
welcome as issues — failed attacks are evidence too.
歡迎任何人嘗試證偽：復原已刪內容、或弄斷倖存段的鏈。成功或失敗的攻擊紀錄都歡迎開 issue——失敗的攻擊也是證據。
