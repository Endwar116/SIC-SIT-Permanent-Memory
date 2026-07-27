#!/usr/bin/env python3
"""VS-9 Phase 5 測試：Dedup 三分法（T 場景：合併不升版/演化升版/平行不去重）
預測（執行前落盤）：
  DD1 完全相同 primitives＋同 causal_chain          → MERGE
  DD2 小幅 state 變化＋同 task(id+deliverable)      → VERSION_UPDATE
  【首跑記錄】DD2 首跑=MERGE（5/6）：暴露規格縫隙——merge只動metadata收不了核心變化，>0.92同身份+核心有異=靜默丟資訊；修=MERGE加核心deep-equal前提（Q14候覆核）
  DD3 完全不同內容                                  → WRITE_NEW
  DD4 幾乎相同但 task.id 不同                        → WRITE_NEW（P-3 平行非重複）
  DD5 相似度序：identical=1.0 > similar > different
  DD6 端到端：MERGE 走 mutation.merge 版本不動；VERSION_UPDATE 走 mutation.version_update 版本+1
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dedup
import mutation as mu
from tests_phase1_base import BASE

results = []


def check(name, expect, got):
    ok = expect == got
    results.append(ok)
    print(f"{'✅' if ok else '❌'} {name}: 預測={expect} 實際={got}")


def mk(task=None, state_val="phase1 test", chain=None, uid="mu-bbbbbbbb"):
    u = copy.deepcopy(BASE)
    u["id"] = uid
    u["dna"]["primitives"]["state"][0]["value"] = state_val
    u["dna"]["primitives"]["task"] = task
    u["dna"]["causal_chain"] = chain or []
    return u


TASK = {"id": "VS-9", "title": "橋接", "deliverable": "Phase 5", "status": "in_progress", "created_round": 1}
TASK_OTHER = {"id": "VS-4", "title": "治理", "deliverable": "Phase 5", "status": "in_progress", "created_round": 1}

lib = [mk(task=TASK, chain=["t1", "p1", "o1"], uid="mu-lib00001")]

# DD1：identical+同chain
r = dedup.decide(mk(task=TASK, chain=["t1", "p1", "o1"]), lib)
check("DD1", "MERGE", r["action"])
# DD2：state 小變+同 task
r2 = dedup.decide(mk(task=TASK, state_val="phase1 test 但推進到 dedup 完成", chain=["t1", "p1", "o2"]), lib)
check("DD2", "VERSION_UPDATE", r2["action"])
# DD3：完全不同
u3 = mk(task=None, state_val="完全無關：VJ視覺頻段18態")
u3["dna"]["primitives"]["entity"] = [{"id": "e9", "type": "topic", "value": "SIC-VJ"}]
u3["dna"]["primitives"]["intent"] = [{"actor": "e9", "direction": "render"}]
r3 = dedup.decide(u3, lib)
check("DD3", "WRITE_NEW", r3["action"])
# DD4：幾乎相同但 task.id 不同（P-3）
r4 = dedup.decide(mk(task=TASK_OTHER, chain=["t1", "p1", "o1"]), lib)
check("DD4", "WRITE_NEW", r4["action"])
# DD5：相似度序
s_id = dedup.similarity(mk(task=TASK, chain=["t1"]), mk(task=TASK, chain=["t1"]))
s_sim = dedup.similarity(mk(task=TASK), mk(task=TASK, state_val="phase1 test 但推進到 dedup"))
s_diff = dedup.similarity(mk(task=TASK), u3)
check("DD5", True, s_id == 1.0 and s_id > s_sim > s_diff)
# DD6：端到端接 mutation
target = lib[0]
merged = mu.merge(target, weight_dynamic_value=0.4)
vu = mu.version_update(target, new_primitives={"state": [{"dimension": "context", "value": "演化後"}]},
                       change_summary="dedup VERSION_UPDATE 路徑")
check("DD6", (1, 2), (merged["version"]["current_number"], vu["version"]["current_number"]))
# DD7（R225 新增）：>0.92 同身份但核心有異 → VERSION_UPDATE（資訊零丟失守門）
u7 = mk(task=TASK, chain=["t1", "p1", "o1"])
u7["dna"]["primitives"]["state"][0]["value"] = "phase1 test!"  # 一字之差
r7 = dedup.decide(u7, lib)
check("DD7", ("VERSION_UPDATE", True), (r7["action"], r7["score"] > 0.92))

hits = sum(results)
print(f"\n預測對照：{hits}/{len(results)} 中")
sys.exit(0 if hits == len(results) else 1)
