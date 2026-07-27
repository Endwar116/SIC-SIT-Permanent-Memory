"""Phase 1 測試共用基準 memory_unit（tests_phase1 / tests_phase1b 共用）"""
BASE = {
    "id": "mu-" + "a" * 8,
    "foundational": False,
    "memory_kind": "episodic",
    "dna": {
        "primitives": {
            "entity": [{"id": "e1", "type": "agent", "value": "maintainer"}],
            "state": [{"dimension": "context", "value": "phase1 test"}],
            "relation": [],
            "event": None,
            "intent": None,
            "task": None,
        },
        "causal_chain": [],
        "rarity_score": 0.0,
        "relation_density": 0.0,
    },
    "version": {"current_number": 1, "current_label": "v1", "branch": "main",
                "created_at": "2026-07-24T13:40:00+08:00", "updated_at": "2026-07-24T13:40:00+08:00", "history": []},
    "weight": {"fixed": {"value": 0.0, "set_by": "system", "immutable": True},
               "dynamic": {"value": 0.1, "decay_on_repeat": True, "decay_rate": 0.1},
               "combined": 0.1},
    "storage": {"layer": "background", "compression_state": "none", "retention_class": "deletable",
                "vault_candidate_expires": None, "integrity_signature": None},
    "semantic_fold": {"original_ref": None, "fold_summary": {}},
    "provenance": {"owner": "maintainer", "source_id": "selftest"},
    "audit_trail": [],
}
