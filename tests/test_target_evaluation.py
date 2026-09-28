"""
Tests for target evaluators, target projection and invalidation rules.
"""

from decimal import Decimal

import pytest

from tradingbot.domain import Candle, StateTransition
from tradingbot.domain.enums import (
    InvalidationStatus,
    SetupDirection,
    TargetEvaluationMode,
)
from tradingbot.strategy.invalidation import (
    NoInvalidationRule,
    ReferenceInvalidationRule,
    build_invalidation_rule,
)
from tradingbot.strategy.target_evaluator import (
    CloseReachEvaluator,
    HighLowReachEvaluator,
    build_target_evaluator,
)
from tradingbot.strategy.target_projection import (
    CAnchoredRatioTargetProjector,
    IdentityTargetProjector,
    build_target_projector,
)


def _candle(high, low, close, ts=1000):
    return Candle(
        timestamp=ts,
        open=Decimal(str((high + low) / 2)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(1),
    )


class TestHighLowReach:
    def test_long_high_touches_target(self):
        ev = HighLowReachEvaluator()
        assert ev.evaluate(Decimal(105), SetupDirection.LONG,
                           _candle(high=105, low=95, close=100)) is True

    def test_long_high_below_target(self):
        ev = HighLowReachEvaluator()
        assert ev.evaluate(Decimal("105.01"), SetupDirection.LONG,
                           _candle(high=105, low=95, close=100)) is False

    def test_short_low_undercuts_target(self):
        ev = HighLowReachEvaluator()
        assert ev.evaluate(Decimal(95), SetupDirection.SHORT,
                           _candle(high=105, low=95, close=100)) is True

    def test_short_low_above_target(self):
        ev = HighLowReachEvaluator()
        assert ev.evaluate(Decimal("94.99"), SetupDirection.SHORT,
                           _candle(high=105, low=95, close=100)) is False

    def test_mode_enum(self):
        assert HighLowReachEvaluator().mode == TargetEvaluationMode.HIGH_LOW_REACH


class TestCloseReach:
    def test_long_close_at_or_above(self):
        ev = CloseReachEvaluator()
        assert ev.evaluate(Decimal(100), SetupDirection.LONG,
                           _candle(high=101, low=99, close=100)) is True

    def test_long_touch_without_close_fails(self):
        ev = CloseReachEvaluator()
        assert ev.evaluate(Decimal("100.5"), SetupDirection.LONG,
                           _candle(high=101, low=99, close=100)) is False

    def test_short_close_at_or_below(self):
        ev = CloseReachEvaluator()
        assert ev.evaluate(Decimal(100), SetupDirection.SHORT,
                           _candle(high=101, low=99, close=100)) is True

    def test_mode_enum(self):
        assert CloseReachEvaluator().mode == TargetEvaluationMode.CLOSE_REACH


class TestFactory:
    def test_build_by_enum(self):
        assert isinstance(build_target_evaluator(TargetEvaluationMode.CLOSE_REACH),
                          CloseReachEvaluator)
        assert isinstance(build_target_evaluator("high_low_reach"),
                          HighLowReachEvaluator)

    def test_build_unknown_raises(self):
        with pytest.raises(ValueError):
            build_target_evaluator("made_up_mode")


class TestTargetProjection:
    def test_c_anchored_long_multiplies(self):
        p = CAnchoredRatioTargetProjector()
        assert p.project(Decimal("2.75"), SetupDirection.LONG,
                         Decimal(100), Decimal(150), Decimal(125)) == Decimal("343.7500")

    def test_c_anchored_short_divides(self):
        p = CAnchoredRatioTargetProjector()
        result = p.project(Decimal("2"), SetupDirection.SHORT,
                           Decimal(100), Decimal(150), Decimal(125))
        assert result == Decimal("62.5")

    def test_identity_passthrough(self):
        p = IdentityTargetProjector()
        assert p.project(Decimal("2.75"), SetupDirection.LONG,
                         Decimal(100), Decimal(150), Decimal(125)) == Decimal("2.75")

    def test_factory(self):
        assert isinstance(build_target_projector("identity"), IdentityTargetProjector)
        with pytest.raises(ValueError):
            build_target_projector("nope")

    def test_describe_mentions_interpretation(self):
        d = CAnchoredRatioTargetProjector().describe()
        assert "REFERENCE INTERPRETATION" in d["interpretation"]


class TestReferenceInvalidation:
    def test_long_invalidated_below_c(self):
        rule = ReferenceInvalidationRule(max_candles_active=10)
        setup_c = Decimal(90)
        candle = _candle(high=95, low=89, close=92, ts=2000)

        class FakeSetup:
            direction = SetupDirection.LONG
            c = type("P", (), {"value": setup_c})()

        assert rule.check(FakeSetup(), candle, 1) == InvalidationStatus.INVALIDATED

    def test_long_survives_above_c(self):
        rule = ReferenceInvalidationRule(max_candles_active=10)
        setup_c = Decimal(90)
        candle = _candle(high=95, low=91, close=92, ts=2000)

        class FakeSetup:
            direction = SetupDirection.LONG
            c = type("P", (), {"value": setup_c})()

        assert rule.check(FakeSetup(), candle, 1) is None

    def test_short_invalidated_above_c(self):
        rule = ReferenceInvalidationRule(max_candles_active=10)
        candle = _candle(high=111, low=105, close=108, ts=2000)

        class FakeSetup:
            direction = SetupDirection.SHORT
            c = type("P", (), {"value": Decimal(110)})()

        assert rule.check(FakeSetup(), candle, 1) == InvalidationStatus.INVALIDATED

    def test_expiry_after_max_candles(self):
        rule = ReferenceInvalidationRule(max_candles_active=3)
        candle = _candle(high=95, low=91, close=92, ts=2000)

        class FakeSetup:
            direction = SetupDirection.LONG
            c = type("P", (), {"value": Decimal(90)})()

        assert rule.check(FakeSetup(), candle, 3) == InvalidationStatus.EXPIRED
        assert rule.check(FakeSetup(), candle, 2) is None

    def test_invalid_max_candles(self):
        with pytest.raises(ValueError):
            ReferenceInvalidationRule(max_candles_active=0)


class TestNoInvalidation:
    def test_only_expiry_applies(self):
        rule = NoInvalidationRule(max_candles_active=5)
        candle = _candle(high=1, low=0.5, close=1, ts=2000)

        class FakeSetup:
            direction = SetupDirection.LONG
            c = type("P", (), {"value": Decimal(90)})()

        assert rule.check(FakeSetup(), candle, 1) is None
        assert rule.check(FakeSetup(), candle, 5) == InvalidationStatus.EXPIRED


class TestBuildInvalidation:
    def test_factory_kinds(self):
        assert isinstance(build_invalidation_rule("reference"), ReferenceInvalidationRule)
        assert isinstance(build_invalidation_rule("none"), NoInvalidationRule)
        with pytest.raises(ValueError):
            build_invalidation_rule("mystery")


class TestStateTransition:
    def test_requires_reason(self):
        with pytest.raises(ValueError):
            StateTransition(timestamp=1, previous_state="a", new_state="b", reason="")

    def test_to_dict(self):
        t = StateTransition(timestamp=5, previous_state="pending",
                            new_state="active", reason="activation", candle_index=3)
        d = t.to_dict()
        assert d["previous_state"] == "pending"
        assert d["new_state"] == "active"
        assert d["candle_index"] == 3
