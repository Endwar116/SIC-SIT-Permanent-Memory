#!/usr/bin/env python3
"""VS-9 Phase 1：memory_unit 分層驗證器 v0.1
L1 = JSON Schema（schema/memory_unit-v0.1.json）
L2 = 跨欄位治理規則（裁定 R-1/R-2＋祖檔 Part 15 欄位規則＋errata #3/#8-C）
設計對齊 canonical sic_validate.py 的分層形式（讀碼比對 2026-07-24）。
"""
import json
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).parent / "schema" / "memory_unit-v0.1.json"
_SCHEMA = json.load(open(SCHEMA_PATH, encoding="utf-8"))
_V = Draft7Validator(_SCHEMA)

TERMINAL = {"completed", "dismissed", "archived"}


def validate_unit(u: dict, ruling_exists=None) -> dict:
    """ruling_exists：可選 callable(audit_id)->bool——R-2 裁定真偽回查（F7 根治）。"""
    res = {"status": "PASS", "errors": [], "warnings": []}

    def fail(rule, msg):
        res["status"] = "FAIL"
        res["errors"].append({"rule": rule, "message": msg})

    # L1 schema
    schema_errs = sorted(_V.iter_errors(u), key=lambda e: e.path)
    if schema_errs:
        for e in schema_errs[:5]:
            fail("schema", f"{list(e.absolute_path)}: {e.message[:100]}")
        return res

    prim = u["dna"]["primitives"]
    task = prim["task"]
    storage = u["storage"]
    kind = u["memory_kind"]

    # R-2：終態 task 需裁定 audit 引用（寫入順序：裁定 audit 先入外部 store 取 id）
    if task is not None and task["status"] in TERMINAL:
        has_ruling = any(
            a.get("audit_type") == "task_terminal_ruling" and a.get("details", {}).get("ruling_audit_id")
            for a in u["audit_trail"]
        )
        if not has_ruling:
            fail("R-2", f"task.status={task['status']} 但 audit_trail 無 task_terminal_ruling（含 ruling_audit_id）——記憶不能記載沒有裁定依據的任務關閉")
        elif ruling_exists is not None:
            rid = next(a["details"]["ruling_audit_id"] for a in u["audit_trail"]
                       if a.get("audit_type") == "task_terminal_ruling")
            if not ruling_exists(rid):
                fail("R-2-verify", f"ruling_audit_id={rid} 在鏈式 audit store 查無此裁定——偽造裁定攻擊面（F7）攔截")

    # anchor 規則（errata #3 / #8-C）
    if kind == "anchor":
        if not u["foundational"]:
            fail("anchor", "anchor 類記憶 foundational 必須為 true（系統創建預設）")
        if storage["retention_class"] != "immutable":
            fail("anchor", "anchor 類記憶 retention_class 必須 immutable")

    # 簽名欄位：只有 vault + immutable 有值
    if storage["integrity_signature"] is not None:
        if not (storage["layer"] == "vault" and storage["retention_class"] == "immutable"):
            fail("signature", "integrity_signature 只允許 vault+immutable 記憶持有")

    # vault_candidate 必有到期時間（errata #9）
    if storage["layer"] == "vault_candidate" and storage["vault_candidate_expires"] is None:
        fail("candidate", "vault_candidate 層必須設 vault_candidate_expires")

    # vault 記憶必須已簽名
    if storage["layer"] == "vault" and storage["integrity_signature"] is None:
        fail("vault", "vault 層記憶必須攜帶 integrity_signature")

    # combined 一致性（衍生值，警告不擋）
    fx, dy = u["weight"]["fixed"]["value"], u["weight"]["dynamic"]["value"]
    if abs(u["weight"]["combined"] - (fx + dy)) > 1e-9:
        res["warnings"].append({"rule": "weight", "message": f"combined({u['weight']['combined']}) != fixed+dynamic({fx + dy})"})
        if res["status"] == "PASS":
            res["status"] = "WARN"

    # 檢索豁免提示（ingest 規格 §五-2 的下游義務）
    if u["provenance"].get("handshake_secret"):
        res["warnings"].append({"rule": "retrieval", "message": "handshake_secret=true：檢索層必須豁免召回（Part 17 filter 義務）"})
        if res["status"] == "PASS":
            res["status"] = "WARN"

    return res


if __name__ == "__main__":
    import sys

    r = validate_unit(json.load(open(sys.argv[1], encoding="utf-8")))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(1 if r["status"] == "FAIL" else 0)
