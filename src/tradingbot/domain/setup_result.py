"""
SetupResult: outcome record of a single tracked ABC setup in a backtest.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional

from .abc_setup import ABCSetup
from .enums import SetupDirection, SetupStatus, TargetStatus


@dataclass
class SetupResult:
    """Record of one tracked ABC setup and its outcome in a backtest.

    Attributes:
        setup: The ABC setup that was tracked.
        activated_at: Candle timestamp when the setup became active.
        completed_at: Candle timestamp when the setup reached a terminal state.
        final_status: Terminal status (TARGET_REACHED / INVALIDATED / EXPIRED / ACTIVE).
        target_status: Whether the mathematical target was reached.
        invalidation_status: Whether/why the setup was invalidated.
        target: The mathematical target (B + C) / A.
        reached_at: Candle timestamp when the target was reached (if any).
        invalidated_at: Candle timestamp when invalidation occurred (if any).
        expiry_at: Candle timestamp when expiry occurred (if any).
        candles_monitored: Number of candles evaluated while the setup was active.
        max_favorable_excursion: Best price movement toward the target (0 if none).
        max_adverse_excursion: Worst price movement against the setup (0 if none).
        gross_outcome: Directional price outcome fraction (informational only).
        cost_impact: Absolute estimated cost from the cost model (informational only).
        state_transitions: Recorded lifecycle transitions.
        setup_id: Stable per-run setup identifier assigned by the engine (for UIs).
    """
    setup: ABCSetup
    setup_id: Optional[int] = None
    activated_at: Optional[int] = None
    completed_at: Optional[int] = None
    final_status: SetupStatus = SetupStatus.ACTIVE
    target_status: TargetStatus = TargetStatus.NOT_EVALUATED
    invalidation_status: Any = None
    target: Optional[Decimal] = None
    reached_at: Optional[int] = None
    invalidated_at: Optional[int] = None
    expiry_at: Optional[int] = None
    candles_monitored: int = 0
    max_favorable_excursion: Decimal = Decimal('0')
    max_adverse_excursion: Decimal = Decimal('0')
    gross_outcome: Optional[Decimal] = None
    cost_impact: Decimal = Decimal('0')
    state_transitions: list = field(default_factory=list)

    @property
    def direction(self) -> SetupDirection:
        return self.setup.direction

    def duration_ms(self) -> Optional[int]:
        """Duration from activation to completion in milliseconds (None if still active)."""
        if self.activated_at is None or self.completed_at is None:
            return None
        return self.completed_at - self.activated_at

    def is_terminal(self) -> bool:
        """True if the setup reached a terminal status."""
        return self.final_status in (
            SetupStatus.TARGET_REACHED,
            SetupStatus.INVALIDATED,
            SetupStatus.EXPIRED,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "setup_id": self.setup_id,
            "direction": self.setup.direction.value,
            "a": self.setup.a.to_dict(),
            "b": self.setup.b.to_dict(),
            "c": self.setup.c.to_dict(),
            "target": str(self.target) if self.target is not None else None,
            "activated_at": self.activated_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms(),
            "final_status": self.final_status.value,
            "target_status": self.target_status.value,
            "invalidation_status": (
                self.invalidation_status.value
                if hasattr(self.invalidation_status, "value")
                else self.invalidation_status
            ),
            "reached_at": self.reached_at,
            "invalidated_at": self.invalidated_at,
            "expiry_at": self.expiry_at,
            "candles_monitored": self.candles_monitored,
            "max_favorable_excursion": str(self.max_favorable_excursion),
            "max_adverse_excursion": str(self.max_adverse_excursion),
            "gross_outcome": str(self.gross_outcome) if self.gross_outcome is not None else None,
            "cost_impact": str(self.cost_impact),
            "state_transitions": [t.to_dict() if hasattr(t, "to_dict") else t for t in self.state_transitions],
            "setup_metadata": dict(self.setup.metadata),
        }
