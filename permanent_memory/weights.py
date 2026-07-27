#!/usr/bin/env python3
"""VS-9 Phase 2：動態權重 v0.1（祖檔 Part 9）
核心命題：真實影響 ≠ 重複次數。重複出現無新影響 → dynamic_weight 下降。
DECAY_RATE=0.1 為 Part 9.2 預設 [BOOTSTRAPPED]——E4 驗證或改進；E4 定性判準（Part 9.4 原文例）：
「說要死沒死」30 次 → 權重趨近 0 → 不觸發 vault_candidate。
"""

DECAY_RATE_DEFAULT = 0.1  # [BOOTSTRAPPED] E4 校準對象


def real_impact(led_to_decision_change=False, referenced_by_high_weight=False,
                in_task_execution_chain=False, created_new_relation=False) -> float:
    """Part 9.3 階梯（原文順序=優先序）。全 False = 只被查詢無後續影響 = 0.1。"""
    if led_to_decision_change:
        return 0.8
    if referenced_by_high_weight:
        return 0.6
    if in_task_execution_chain:
        return 0.5
    if created_new_relation:
        return 0.4
    return 0.1


def apply_decay_on_repeat(dynamic_value: float, signal_count: int,
                          decay_rate: float = DECAY_RATE_DEFAULT) -> float:
    """Part 9.4 公式原樣：value * (1-decay)^(count-1)，下限 0。"""
    if signal_count <= 1:
        return dynamic_value
    return max(0.0, dynamic_value * (1 - decay_rate) ** (signal_count - 1))
