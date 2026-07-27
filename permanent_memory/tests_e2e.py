#!/usr/bin/env python3
"""VS-9 端到端測試（Gate→Verbatim→Store 全鏈＋F34 owner 分區）
預測（執行前落盤；E3 曾在寫測試時自打架，跑前重推流向修正——跑後即凍結）：
  E1 正常句+單元 → PASS＋WRITE_NEW＋original_ref 指回 verbatim 且解密==原文
  E2 噪音 → DISCARD＋verbatim 有＋units 仍 1
  E3 dup 句×4（primitives 與 E1 恆等）→ 前三次 PASS 但 store 端 MERGE 進 E1、第4次 gate AGGREGATE
     → r3=AGGREGATE、units 仍 1（gate 與 store 兩層去重各自作用的證明）
  E4 F34：primitives 恆等但 owner=agentB → WRITE_NEW、units=2（不跨 owner 合併）
  E5 owner=agentA 恆等 → MERGE、units 仍 2
  E7 WRITE_NEW 撞 id → REJECTED 不覆蓋（F37 修驗證）
  E6 verbatim 條數=9（全輸入含噪音與撞號句）＋鏈驗 ok＋units=2
"""
import copy
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import verbatim_store as vs

TD = Path(__file__).parent / "data_test_e2e"
vs.DATA, vs.SEGS, vs.KEYS = TD, TD / "verbatim", TD / "keys"
vs.AUDIT, vs.REGISTRY = TD / "audit.jsonl", TD / "keys" / "keys_registry.json"
if TD.exists():
    _old = TD.parent / "data_test_e2e_old"; _old.mkdir(exist_ok=True)
    shutil.move(str(TD), str(_old / f"run_{len(list(_old.iterdir()))}"))

import gate
from pipeline import Pipeline
from store import MemoryStore
from tests_phase1_base import BASE

results = []
SEG = "2026-07E"
inputs = 0


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


def mk(uid, owner="agentA"):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["provenance"]["owner"] = owner
    u["provenance"]["source_id"] = "e2e"
    u["dna"]["primitives"]["state"][0]["value"] = "端到端測試句"
    u["dna"]["causal_chain"] = ["t", "p", "o"]
    return u


P = Pipeline(gate.PreMemoryGate(), MemoryStore(TD / "store"))

# E1
r1 = P.ingest("代理人甲說：完成不能自己定義。", unit=mk("mu-e2e00001"), segment=SEG); inputs += 1
u1 = P.store.get("mu-e2e00001")
check("E1", ("PASS", "WRITE_NEW", f"{SEG}:0", "代理人甲說：完成不能自己定義。"),
      (r1["gate_action"], r1["store_result"]["action"], u1["semantic_fold"]["original_ref"],
       vs.read(r1["verbatim"]["segment"], r1["verbatim"]["seq"])))
# E2
r2 = P.ingest("。。。", unit=mk("mu-e2enoise"), segment=SEG); inputs += 1
check("E2", ("DISCARD", None, 1), (r2["gate_action"], r2["store_result"], len(P.store.load_all())))
# E3
r3 = None
for _ in range(4):
    r3 = P.ingest("同一句重複的信號。", unit=mk("mu-e2e0dup"), segment=SEG); inputs += 1
check("E3", ("AGGREGATE", 1), (r3["gate_action"], len(P.store.load_all())))
# E4
r4 = P.ingest("代理人甲說：完成不能自己定義！", unit=mk("mu-e2e00004", owner="agentB"), segment=SEG); inputs += 1
check("E4", ("WRITE_NEW", 2), (r4["store_result"]["action"], len(P.store.load_all())))
# E5
r5 = P.ingest("代理人甲說：完成不能自己定義？", unit=mk("mu-e2e00005"), segment=SEG); inputs += 1
check("E5", ("MERGE", 2), (r5["store_result"]["action"], len(P.store.load_all())))
# E7（F37 修驗證）：WRITE_NEW 撞既有 id → REJECTED 不覆蓋（預測：REJECTED＋原單元不變）
u7 = mk("mu-e2e00004", owner="agentC")  # 不同 owner→dedup 分區→WRITE_NEW 路徑→撞 id
u7["dna"]["primitives"]["state"][0]["value"] = "企圖覆蓋"
r7 = P.ingest("撞號攻擊句。", unit=u7, segment=SEG); inputs += 1
orig = P.store.get("mu-e2e00004")
check("E7", ("REJECTED", "端到端測試句"), (r7["store_result"]["action"], orig["dna"]["primitives"]["state"][0]["value"]))
# E6
v = vs.verify_chain(SEG)
check("E6", (True, 9, 2), (v["ok"], v["entries"], len(P.store.load_all())))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
