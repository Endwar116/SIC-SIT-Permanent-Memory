#!/usr/bin/env python3
"""wire SIC-JS → 記憶 DNA 折疊 v0.1（ingest 最後一塊：協議形→記憶形）
wire entity {name,model} → DNA entity [{id,type,value}]；state {context,current_action} → 維度陣列；
relation {user,upstream,...} → 邊陣列；event/intent 物件 → 陣列；task 原樣（null 語義記憶側 fail-closed）。"""

def fold(wire: dict) -> dict:
    ent = wire.get("entity") or {}
    st = wire.get("state") or {}
    rel = wire.get("relation") or {}
    ev = wire.get("event")
    it = wire.get("intent")
    prim = {
        "entity": [{"id": ent.get("name", "?"), "type": "agent",
                     "value": f"{ent.get('name','?')}（{ent.get('model','unrecorded')}）"}],
        "state": [{"dimension": "context", "value": str(st.get("context", ""))},
                   {"dimension": "current_action", "value": str(st.get("current_action") or "")}],
        "relation": ([{"from": ent.get("name", "?"), "to": rel.get("user", "?"), "type": "collaborates"}]
                     if rel.get("user") else []),
        "event": ([{"timestamp": ev.get("timestamp", ""), "description": ev.get("description", ""),
                     "trigger": ev.get("trigger", "")}] if isinstance(ev, dict) else None),
        "intent": ([{"actor": ent.get("name", "?"), "direction": "work",
                      "user_intent": it.get("user_intent", ""), "system_intent": it.get("system_intent", "")}]
                   if isinstance(it, dict) else None),
        "task": wire.get("task"),
    }
    return prim
