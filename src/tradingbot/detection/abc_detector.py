"""
A/B/C structure detection.

STRATEGY BOUNDARY — READ CAREFULLY:
The exact original rules for identifying A, B and C from market candles are NOT
confirmed. Everything in this module is a CONFIGURABLE REFERENCE INTERPRETATION,
provided so the system is runnable and testable. It is designed to be replaced
by the exact rules when they are defined. See docs/strategy.md and
docs/assumptions.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..domain import ABCSetup, Candle, PricePoint
from ..domain.enums import SetupDirection, SetupStatus
from .swing_detector import SwingDetector, SwingDetectorConfig, SwingPoint

ZERO = Decimal('0')


@dataclass
class ABCDetectorConfig:
    """Configuration for the ReferenceABCDetector.

    All values here encode reference assumptions, NOT confirmed strategy rules.

    Attributes:
        swing_config: Underlying swing detection parameters (sensitivity).
        min_distance: Minimum price distance (in absolute price units) between
            consecutive structural points (A->B, B->C) for a valid setup.
            0 disables the constraint.
        require_alternation: If True, B must have the opposite role of A
            (A high -> B low for long setups; mirror for shorts).
        max_setups_per_combination: Maximum setups tracked per (direction,
            C index) combination; prevents duplicate setup creation.
        allow_overlapping: If True, a new setup may start while previous setups
            of the same direction are still active.
    """
    swing_config: SwingDetectorConfig = field(default_factory=SwingDetectorConfig)
    min_distance: Decimal = ZERO
    require_alternation: bool = True
    max_setups_per_combination: int = 1
    allow_overlapping: bool = True

    def __post_init__(self):
        if not isinstance(self.min_distance, Decimal):
            self.min_distance = Decimal(str(self.min_distance))
        if self.min_distance < ZERO:
            raise ValueError("min_distance must be >= 0")
        if self.max_setups_per_combination < 1:
            raise ValueError("max_setups_per_combination must be >= 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left_window": self.swing_config.left_window,
            "right_window": self.swing_config.right_window,
            "min_separation": self.swing_config.min_separation,
            "min_distance": str(self.min_distance),
            "require_alternation": self.require_alternation,
            "max_setups_per_combination": self.max_setups_per_combination,
            "allow_overlapping": self.allow_overlapping,
        }


class ABCDetector(ABC):
    """Interface for A/B/C structure detectors.

    Implementations must be:
    * deterministic: same candles + config -> same setups,
    * chronological: a setup must never rely on data after its C point,
    * incremental-friendly: the backtest feeds candles one by one.
    """

    @abstractmethod
    def on_candle(self, candle: Candle) -> List[ABCSetup]:
        """Feed one candle in chronological order; return newly created setups."""
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        """Reset all internal state."""
        raise NotImplementedError

    @property
    @abstractmethod
    def config_summary(self) -> Dict[str, Any]:
        """Return the detector configuration for reporting."""
        raise NotImplementedError


class ReferenceABCDetector(ABCDetector):
    """Deterministic, configurable reference A/B/C detector.

    REFERENCE INTERPRETATION (documented assumption, NOT the confirmed rule):

    * Swing points are detected with :class:`SwingDetector` (configurable
      left/right windows and minimum separation).
    * LONG setups: A = the latest confirmed swing LOW, B = the most recent
      confirmed swing HIGH formed after A, C = the most recent confirmed swing
      LOW formed after B (an up-wave A->B followed by a pullback to C).
    * SHORT setups: mirrored (A = swing HIGH, B = swing LOW, C = swing HIGH).
    * A setup is created when C is confirmed and:
        - C is after B, and B is after A (strict index ordering),
        - optionally, price distances satisfy ``min_distance``,
        - optionally, A/B roles alternate (``require_alternation``).
    * The setup becomes available for activation at the candle where C is
      confirmed — never before. This is the only point where the detector
      makes the setup knowable.

    Replace this class with the exact A/B/C rules when they are defined; the
    mathematical engine, target evaluation and backtesting remain unchanged.
    """

    def __init__(self, config: Optional[ABCDetectorConfig] = None):
        self.config = config or ABCDetectorConfig()
        self._swing_detector = SwingDetector(self.config.swing_config)
        self._swing_highs: List[SwingPoint] = []  # confirmed, in confirmation order
        self._swing_lows: List[SwingPoint] = []
        self._created_keys: set = set()  # (direction, c_point_index) dedupe keys

    # ------------------------------------------------------------------
    # ABCDetector interface
    # ------------------------------------------------------------------
    def on_candle(self, candle: Candle) -> List[ABCSetup]:
        new_setups: List[ABCSetup] = []
        for swing in self._swing_detector.on_candle(candle):
            if swing.is_high:
                self._swing_highs.append(swing)
            else:
                self._swing_lows.append(swing)
            new_setups.extend(self._try_form_setups())
        return new_setups

    def reset(self) -> None:
        self._swing_detector.reset()
        self._swing_highs = []
        self._swing_lows = []
        self._created_keys = set()

    @property
    def config_summary(self) -> Dict[str, Any]:
        summary = self.config.to_dict()
        summary["detector_class"] = type(self).__name__
        return summary

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _try_form_setups(self) -> List[ABCSetup]:
        """Attempt to form setups from the latest confirmed swing sequences."""
        setups: List[ABCSetup] = []
        setups.extend(self._try_form_direction(SetupDirection.LONG))
        setups.extend(self._try_form_direction(SetupDirection.SHORT))
        return setups

    def _try_form_direction(self, direction: SetupDirection) -> List[ABCSetup]:
        """Attempt to form one setup for a direction from confirmed swings.

        LONG:  A = swing low, B = swing high, C = swing low (up-wave then pullback).
        SHORT: A = swing high, B = swing low, C = swing high (down-wave then retrace).

        The trigger is C being CONFIRMED after B was confirmed. Because all
        swings in the lists are already confirmed by the current candle, using
        historical confirmation metadata involves no look-ahead.
        """
        if direction == SetupDirection.LONG:
            firsts, middles = self._swing_lows, self._swing_highs  # A/C role, B role
        else:
            firsts, middles = self._swing_highs, self._swing_lows  # A/C role, B role

        if not firsts or not middles:
            return []

        c = firsts[-1]
        b_last = middles[-1]
        # C must have been confirmed strictly after B was confirmed.
        if c.confirmed_at_index <= b_last.confirmed_at_index:
            return []

        b = self._latest_point_before(list(reversed(middles)), c)
        if b is None:
            return []
        a = self._latest_point_before(list(reversed(firsts)), b)
        if a is None:
            return []

        # Strict chronological ordering by point index.
        if not (a.point_index < b.point_index < c.point_index):
            return []

        if self.config.require_alternation:
            if direction == SetupDirection.LONG:
                if not (a.is_low and b.is_high and c.is_low):
                    return []
            else:
                if not (a.is_high and b.is_low and c.is_high):
                    return []

        if self.config.min_distance > ZERO:
            dist_ab = abs(b.value - a.value)
            dist_bc = abs(b.value - c.value)
            if dist_ab < self.config.min_distance or dist_bc < self.config.min_distance:
                return []

        # Duplicate prevention: one setup per (direction, C point index).
        # When overlapping setups are disallowed, a new setup replaces the
        # previous one of the same direction (the backtest engine also enforces
        # its own concurrency policy).
        key = (direction.value, c.point_index)
        if key in self._created_keys:
            return []
        self._created_keys.add(key)

        a_point = self._to_price_point(a, role='A')
        b_point = self._to_price_point(b, role='B')
        c_point = self._to_price_point(c, role='C')

        # Availability time: when C was confirmed (the detector may only reveal
        # the setup at/after this candle).
        available_at_index = c.confirmed_at_index

        setup = ABCSetup(
            a=a_point,
            b=b_point,
            c=c_point,
            direction=direction,
            status=SetupStatus.PENDING,
            created_at=c.confirmed_at_timestamp,
            metadata={
                "detector": type(self).__name__,
                "available_at_index": available_at_index,
                "a_swing_point_index": a.point_index,
                "b_swing_point_index": b.point_index,
                "c_swing_point_index": c.point_index,
                "c_confirmed_at_index": c.confirmed_at_index,
                "c_confirmed_at_timestamp": c.confirmed_at_timestamp,
            },
        )
        return [setup]

    @staticmethod
    def _latest_point_before(candidates: List[SwingPoint], c: SwingPoint) -> Optional[SwingPoint]:
        """Most recent candidate swing whose POINT index precedes C's point index."""
        for swing in candidates:
            if swing.point_index < c.point_index:
                return swing
        return None

    @staticmethod
    def _to_price_point(swing: SwingPoint, role: str) -> PricePoint:
        return PricePoint(
            value=swing.value,
            timestamp=swing.point_timestamp,
            source="reference_abc_detector",
            candle_index=swing.point_index,
            role=role,
            metadata={
                "swing_role": swing.role.value,
                "confirmed_at_index": swing.corrected_confirmed_index(),
            },
        )
