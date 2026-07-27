#!/usr/bin/env python3
"""壓測 worker：對同一 store 連寫 M 個唯一單元。"""
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from store import MemoryStore
from tests_phase1_base import BASE

wid, m, root = sys.argv[1], int(sys.argv[2]), sys.argv[3]
S = MemoryStore(root)
for j in range(m):
    u = copy.deepcopy(BASE)
    u["id"] = f"mu-w{wid}x{j:04d}"
    u["dna"]["primitives"]["entity"][0]["id"] = f"e-{wid}-{j}"
    u["dna"]["primitives"]["entity"][0]["value"] = f"實體{wid}號{j}"
    u["dna"]["primitives"]["task"] = {"id": f"ST-{int(wid)*100+j}", "title": f"壓測{wid}-{j}",
                                       "deliverable": f"獨立交付{wid}{j}", "status": "pending", "created_round": 1}
    u["dna"]["primitives"]["state"][0]["value"] = f"worker {wid} 第 {j} 筆：主題各異——{'加密'if j%3==0 else '議事'if j%3==1 else '權重'}層的{j}項工作紀錄與細節敘述{wid*3}"
    u["dna"]["causal_chain"] = [f"stress-{wid}-{j}"]
    S.write(u)
print(f"worker {wid} done")
