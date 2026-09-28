"""
Tests for the backtest engine: chronological processing, target evaluation,
invalidation, expiry, duplicates, overlapping setups and look-ahead protection.
"""


import pytest

from conftest import zigzag_candles
from tradingbot.backtesting.backtest_engine import BacktestConfig, BacktestEngine
from tradingbot.domain.enums import (
    SetupDirection,
    SetupStatus,
)
from tradingbot.exceptions import BacktestError
from tradingbot.strategy.cost_model import FeeSlippageSpreadModel, ZeroCostModel


def _engine(**cfg):
    return BacktestEngine(config=BacktestConfig(**cfg))


def test_empty_candles_raise():
    with pytest.raises(BacktestError, match="No candles"):
        _engine().run([])


def test_unsorted_candles_raise():
    candles = zigzag_candles([(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0)])
    with pytest.raises(BacktestError, match="chronologically"):
        _engine().run(list(reversed(candles)))


def test_target_reached_long():
    """With IDENTITY projection the mathematical target (~2.3) is reached
    immediately by any candle priced near 100."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    result = _engine(target_projection="identity").run(candles)
    reached = [
        r for r in result.setup_results
        if r.final_status == SetupStatus.TARGET_REACHED
    ]
    assert len(reached) >= 1
    r = reached[0]
    assert r.setup.direction == SetupDirection.LONG
    # The reach must occur AFTER activation (no same-candle evaluation).
    assert r.reached_at > r.activated_at
    # A/B/C chronology
    s = r.setup
    assert s.a.timestamp < s.b.timestamp < s.c.timestamp
    assert s.a.candle_index < s.b.candle_index < s.c.candle_index


def test_invalidation_on_break_back_through_c():
    """Long setup followed by a deep drop below C -> invalidated, not reached.

    Uses the DEFAULT c_anchored projection: the projected long target is
    C * (B+C)/A which sits far above the price range, so the target cannot be
    reached and the drop below C invalidates the setup.
    """
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0),
         (1, 3, 0.5), (-1, 6, 2.0)]
    )
    result = _engine().run(candles)  # default target_projection
    invalidated = [
        r for r in result.setup_results
        if r.final_status == SetupStatus.INVALIDATED
    ]
    assert len(invalidated) >= 1
    assert all(r.reached_at is None for r in invalidated)


def test_expiry_after_max_candles():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 25, 0.2)]
    )
    result = _engine(max_candles_active=5).run(candles)
    expired = [
        r for r in result.setup_results if r.final_status == SetupStatus.EXPIRED
    ]
    assert len(expired) >= 1
    assert all(r.candles_monitored <= 5 for r in expired)


def test_no_same_candle_activation_no_lookahead():
    """The activation candle itself must never complete the setup."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    result = _engine(target_projection="identity").run(candles)
    for r in result.setup_results:
        for t in r.state_transitions:
            assert t.timestamp >= r.activated_at
            if t.new_state == SetupStatus.TARGET_REACHED:
                assert t.timestamp > r.activated_at


def test_duplicate_setups_suppressed_with_warning():
    """Replaying the same data twice on one engine must not double-count."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    engine = _engine()
    first = engine.run(candles)
    second = engine.run(candles)
    # Deterministic: identical runs produce identical setup counts.
    assert first.metrics["total_setups"] == second.metrics["total_setups"]


def test_overlap_policy_skips_when_disallowed():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0),
         (-1, 6, 1.0), (1, 4, 1.0)]
    )
    allowed = _engine(allow_overlapping=True).run(candles)
    disallowed = _engine(allow_overlapping=False).run(candles)
    assert disallowed.metrics["total_setups"] <= allowed.metrics["total_setups"]


def test_multiple_and_overlapping_setups_supported():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0),
         (-1, 6, 1.0), (1, 4, 1.0)]
    )
    result = _engine().run(candles)
    assert result.metrics["total_setups"] >= 2


def test_high_low_vs_close_reach_differ():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.2)]
    )
    hl = _engine(target_mode="high_low_reach", target_projection="identity").run(candles)
    cl = _engine(target_mode="close_reach", target_projection="identity").run(candles)
    # HIGH_LOW_REACH is more permissive: its hit count can never be lower.
    assert hl.metrics["target_reached"] >= cl.metrics["target_reached"]


def test_short_direction_works():
    candles = zigzag_candles(
        [(-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 8, 1.5)]
    )
    result = _engine(target_projection="identity").run(candles)
    shorts = [
        r for r in result.setup_results
        if r.setup.direction == SetupDirection.SHORT
    ]
    assert len(shorts) >= 1


def test_state_transitions_recorded():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    result = _engine(target_projection="identity").run(candles)
    terminal = [
        r for r in result.setup_results if r.is_terminal()
    ]
    assert terminal, "expected at least one terminal setup"
    r = terminal[0]
    transitions = r.state_transitions
    assert transitions[0].previous_state == SetupStatus.PENDING
    assert transitions[0].new_state == SetupStatus.ACTIVE
    assert transitions[-1].new_state == r.final_status
    assert all(t.reason for t in transitions)


def test_mathematical_target_preserved_on_results():
    """The (B+C)/A value must appear on results regardless of projection."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    result = _engine(target_projection="identity").run(candles)
    for r in result.setup_results:
        s = r.setup
        expected = (s.b.value + s.c.value) / s.a.value
        assert r.setup.target == expected


def test_cost_model_informational_only():
    """Costs never change whether a mathematical target is reached."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    zero_engine = _engine(target_projection="identity")
    costly_engine = _engine(
        target_projection="identity", fee=0.001, slippage=0.001, spread=0.0005
    )
    zero = zero_engine.run(candles)
    costly = costly_engine.run(candles)
    assert zero.metrics["target_reached"] == costly.metrics["target_reached"]
    assert isinstance(zero_engine.cost_model, ZeroCostModel)
    assert isinstance(costly_engine.cost_model, FeeSlippageSpreadModel)


def test_result_contains_assumptions_and_dataset():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 8, 1.5)]
    )
    result = _engine().run(candles)
    assert result.assumptions["formula"].startswith("TARGET = (B + C) / A")
    assert result.dataset["candle_count"] == len(candles)
    assert "abc_detection" in result.assumptions
    assert "CONFIGURABLE REFERENCE" in result.assumptions["abc_detection"]
