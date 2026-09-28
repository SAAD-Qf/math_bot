"""
StateTransition: auditable lifecycle transition record.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class StateTransition:
    """A single recorded lifecycle transition.

    Attributes:
        timestamp: Candle timestamp (ms) when the transition occurred.
        previous_state: State before the transition.
        new_state: State after the transition.
        reason: Human-readable reason for the transition.
        candle_index: Index of the candle that triggered the transition (optional).
    """
    timestamp: Optional[int]
    previous_state: Any
    new_state: Any
    reason: str
    candle_index: Optional[int] = None

    def __post_init__(self):
        if not self.reason:
            raise ValueError("StateTransition requires a reason")

    def to_dict(self) -> Dict[str, Any]:
        prev = getattr(self.previous_state, "value", self.previous_state)
        new = getattr(self.new_state, "value", self.new_state)
        return {
            "timestamp": self.timestamp,
            "previous_state": str(prev),
            "new_state": str(new),
            "reason": self.reason,
            "candle_index": self.candle_index,
        }
