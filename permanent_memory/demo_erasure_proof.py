#!/usr/bin/env python3
"""Erasure Proof Demo — delete one record live, with four verifiable proofs.
可證明遺忘展示：現場刪一筆，四項證據。

Run 用法:
    python3 demo_erasure_proof.py --operator "<your name>"

Why this exists: GDPR Art.17 gives the right to erasure; Art.5(2) requires you
to *prove* you did it. Combined: "delete it, AND keep evidence of the deletion."
Technique: cryptographic erasure (key destruction), listed as Purge-level in
NIST SP 800-88. Honest disclosure at the end — read it.

Everything runs in a demo-only segment; no real data is touched.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import verbatim_store

SEG = "DEMO-0000-00"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator", required=True,
                    help="human running the deletion (recorded in the audit trail)")
    args = ap.parse_args()

    print("=" * 64)
    print("  Erasure Proof — delete one record, four proofs 可證明遺忘")
    print("=" * 64)

    print("\n[1] Write a demo record (encrypted at rest)")
    secret = f"demo PII: phone 0900-DEMO-{int(time.time()) % 10000}, address 1 Demo Rd."
    ref = verbatim_store.append(secret, segment=SEG)
    print(f"    stored at {SEG}:{ref['seq']}")

    print("\n[2] Evidence BEFORE deletion")
    print(f"    a. readable: {'OK' if verbatim_store.read(SEG, ref['seq']) == secret else 'FAIL'}")
    print(f"    b. segment hash chain verifies: {verbatim_store.verify_chain(SEG)['ok']}")

    print(f"\n[3] Cryptographic erase (operator={args.operator})")
    verbatim_store.shred(SEG, actor="human", reason=f"erasure demo; operator={args.operator}")
    print("    key zeroized in place; two audit events written")

    print("\n[4] Four proofs AFTER deletion")
    try:
        verbatim_store.read(SEG, ref["seq"])
        ok1 = False
    except Exception as e:
        ok1 = True
        print(f"    proof 1 OK  content unrecoverable ({type(e).__name__}) — it is gone")
    ok2 = verbatim_store.verify_chain(SEG)["ok"]
    print(f"    proof 2 {'OK ' if ok2 else 'FAIL'} the deleted segment's hash chain STILL verifies —")
    print("               'was there ever a record here?' remains answerable")
    ok3 = all(verbatim_store.verify_chain(s)["ok"]
              for s in verbatim_store._registry() if s != SEG) if verbatim_store._registry() else True
    print(f"    proof 3 {'OK ' if ok3 else 'FAIL'} every OTHER segment's chain is unbroken")
    reg = verbatim_store._registry()[SEG]
    ok4 = reg["status"] == "shredded" and len(reg.get("audit", [])) == 2
    print(f"    proof 4 {'OK ' if ok4 else 'FAIL'} the deletion itself left evidence"
          f" (who/when/why, {reg.get('shredded_at', '')[:19]})")

    print("\n" + "=" * 64)
    allok = ok1 and ok2 and ok3 and ok4
    print(f"  RESULT: {'ALL FOUR PROOFS HOLD' if allok else 'A PROOF FAILED'}")
    print("  Mapping: GDPR Art.17 (erasure) + Art.5(2) (accountability) + NIST 800-88 (Purge)")
    print("  Honest disclosure — judge for yourself:")
    print("   * This is CRYPTOGRAPHIC erasure, not physical media sanitization: the")
    print("     ciphertext still exists (that is what keeps the chain verifiable);")
    print("     auditors differ on whether key destruction constitutes legal deletion.")
    print("   * While a process is running, decrypted content is plaintext in RAM;")
    print("     this protects data at rest, not a live memory dump.")
    print("  本展示採用金鑰銷毀而非物理抹除——密文仍在（鏈可驗的代價）；稽核方接受度不一，")
    print("  由審閱者自行判斷。運行中記憶體為明文，本機制保護落盤冷資料。")
    print("=" * 64)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
