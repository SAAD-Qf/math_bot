"""
Swing / pivot detection engine.

CRITICAL — LOOK-AHEAD RULE:
A swing at candle index i with right window N is only *confirmed* once candle
i+N has been processed. The detector exposes two notions of time:

* point_index / point_timestamp: where the swing physically occurred.
* confirmed_at_index / confirmed_at_timestamp: the first candle at which the
  swing becomes knowable (point_index + confirm_right).

Consumers (ABC detectors, backtests) MUST gate availability on
``confirmed_at_index`` to avoid look-ahead bias.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..domain import Candle
from ..domain.enums import PointRole

TWO = Decimal('2')


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed swing (pivot) point.

    Attributes:
        role: SWING_HIGH or SWING_LOW.
        value: The extreme price (high for swing highs, low for swing lows).
        point_index: Candle index where the extreme physically occurred.
        point_timestamp: Candle timestamp (ms) where the extreme occurred.
        confirmed_at_index: Index of the first candle where the swing is knowable.
        confirmed_at_timestamp: Timestamp of the confirmation candle.
        left_window: Left window used for detection.
        right_window: Right window used for confirmation.
        metadata: Extra context (e.g. whether ties were involved).
    """
    role: PointRole
    value: Decimal
    point_index: int
    point_timestamp: int
    confirmed_at_index: int
    confirmed_at_timestamp: int
    left_window: int
    right_window: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high(self) -> bool:
        return self.role == PointRole.SWING_HIGH

    @property
    def is_low(self) -> bool:
        return self.role == PointRole.SWING_LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            'role': self.role.value,
            'value': str(self.value),
            'point_index': self.point_index,
            'point_timestamp': self.point_timestamp,
            'confirmed_at_index': self.corrected_confirmed_index(),
            'confirmed_at_timestamp': self.corrected_confirmed_timestamp(),
            'left_window': self.left_window,
            'right_window': self.right_window,
            'metadata': dict(self.metadata),
        }

    def corrected_confirmed_index(self) -> int:
        return self.confirmed_at_index

    def corrected_confirmed_timestamp(self) -> int:
        return self.confirmed_at_timestamp


@dataclass
class SwingDetectorConfig:
    """Configuration for the SwingDetector.

    Attributes:
        left_window: Number of candles to the left that must be lower (highs) /
            higher (lows) than the candidate extreme. Must be >= 1.
        right_window: Number of candles to the right required to confirm a swing.
            Confirmation delay equals right_window candles. Must be >= 1.
        min_separation: Minimum number of candles between consecutive swings of
            the same role. 0 disables the constraint.
    """
    left_window: int = 3
    right_window: int = 3
    min_separation: int = 1

    def __post_init__(self):
        if self.left_window < 1:
            raise ValueError("left_window must be >= 1")
        if self.right_window < 1:
            raise ValueError("right_window must be >= 1")
        if self.min_separation < 0:
            raise ValueError("min_separation must be >= 0")


class SwingDetector:
    """Detects swing highs and lows with chronological confirmation.

    The detector is incremental: ``on_candle`` is fed candles in chronological
    order and returns only swings *confirmed by that candle*. No future data is
    used before it becomes available.

    Tie-breaking rule (documented assumption): when several candles share the
    same extreme within a window (a plateau), the FIRST such candle is the
    swing point. Implementation: a candidate is rejected if any earlier candle
    in the window has an equal-or-more-extreme value, or if any later candle in
    the right window is strictly more extreme. This makes detection
    deterministic and keeps the swing point at the plateau's first candle.
    """

    def __init__(self, config: Optional[SwingDetectorConfig] = None):
        self.config = config or SwingDetectorConfig()
        self._candles: List[Candle] = []
        self._confirmed_high_indices: List[int] = []
        self._confirmed_low_indices: List[int] = []

    def reset(self) -> None:
        """Clear all state (used between backtest runs)."""
        self._candles = []
        self._confirmed_high_indices = []
        self._confirmed_low_indices = []

    @property
    def candles_seen(self) -> int:
        return len(self._candles)

    def on_candle(self, candle: Candle) -> List[SwingPoint]:
        """Feed one candle and return swings confirmed by this candle.

        Args:
            candle: The next candle in chronological order.

        Returns:
            Swing points whose confirmation index equals the current index.
        """
        self._candles.append(candle)
        i = len(self._candles) - 1
        confirmed: List[SwingPoint] = []

        # A swing at index p is confirmable when i == p + right_window.
        p = i - self.config.right_window
        if p < self.config.left_window:
            return confirmed

        high = self._try_detect_high(p)
        if high is not None:
            confirmed.append(high)
            self._confirmed_high_indices.append(p)
        low = self._try_detect_low(p)
        if low is not None:
            confirmed.append(low)
            self._confirmed_low_indices.append(p)
        return confirmed

    def process_all(self, candles: List[Candle]) -> List[SwingPoint]:
        """Process a full chronological candle list and return all swings
        ordered by confirmation time."""
        all_swings: List[SwingPoint] = []
        for candle in candles:
            all_swings.extend(self.on_candle(candle))
        return all_swings

    def _try_detect_high(self, p: int) -> Optional[SwingPoint]:
        cfg = self.config
        candles = self._candles
        high = candles[p].high

        # Left: no earlier candle may match or exceed the extreme
        # (guarantees the FIRST plateau candle wins).
        for j in range(p - cfg.left_window, p):
            if candles[j].high >= high:
                return None
        # Right window (already fully available since i == p + right_window):
        # no later candle may strictly exceed the extreme.
        for j in range(p + 1, p + cfg.right_window + 1):
            if candles[j].high > high:
                return None

        # min_separation against previous swing highs.
        prev = self._last_high_index_before(p)
        if prev is not None and (p - prev) < cfg.min_separation:
            return None

        return SwingPoint(
            role=PointRole.SWING_HIGH,
            value=high,
            point_index=p,
            point_timestamp=candles[p].timestamp,
            confirmed_at_index=p + cfg.right_window,
            confirmed_at_timestamp=candles[p + cfg.right_window].timestamp,
            left_window=cfg.left_window,
            right_window=cfg.right_window,
            metadata={'tie_break': 'first_extreme_in_window'},
        )

    def _try_detect_low(self, p: int) -> Optional[SwingPoint]:
        cfg = self.config
        candles = self._candles
        low = candles[p].low

        for j in range(p - cfg.left_window, p):
            if candles[j].low <= low:
                return None
        for j in range(p + 1, p + cfg.right_window + 1):
            if candles[j].low < low:
                return None

        prev = self._last_low_index_before(p)
        if prev is not None and (p - prev) < cfg.min_separation:
            return None

        return SwingPoint(
            role=PointRole.SWING_LOW,
            value=low,
            point_index=p,
            point_timestamp=candles[p].timestamp,
            confirmed_at_index=p + cfg.right_window,
            confirmed_at_timestamp=candles[p + cfg.right_window].timestamp,
            left_window=cfg.left_window,
            right_window=cfg.right_window,
            metadata={'tie_break': 'first_extreme_in_window'},
        )

    def _last_high_index_before(self, p: int) -> Optional[int]:
        """Point index of the most recent accepted swing high before p."""
        candidates = [q for q in self._confirmed_high_indices if q < p]
        return max(candidates) if candidates else None

    def _last_low_index_before(self, p: int) -> Optional[int]:
        """Point index of the most recent accepted swing low before p."""
        candidates = [q for q in self._confirmed_low_indices if q < p]
        return max(candidates) if candidates else None
