"""
Replay-stream contract tests.

``run()`` must be exactly ``iter_run()`` + aggregation: one evaluation path for
the CLI, reports and the browser dashboard.
"""

from tradingbot.backtesting.backtest_engine import BacktestConfig, BacktestEngine
from tradingbot.data.csv_data_provider import CSVDataProvider
from tradingbot.domain.enums import SetupStatus

DATASET = "data/sample/sample_sinus_1h.csv"


def _candles():
    return CSVDataProvider(DATASET).get_candles()


def _snapshot(result):
    """Comparable outcome snapshot (duration is wall-clock and excluded)."""
    return {
        "dataset": result.dataset,
        "config": result.config,
        "metrics": result.metrics,
        "warnings": result.warnings,
        "errors": result.errors,
        "assumptions": result.assumptions,
        "setups": [
            {
                "setup_id": r.setup_id,
                "direction": r.setup.direction.value,
                "a": r.setup.a.to_dict(),
                "b": r.setup.b.to_dict(),
                "c": r.setup.c.to_dict(),
                "target": str(r.target),
                "activated_at": r.activated_at,
                "completed_at": r.completed_at,
                "final_status": r.final_status.value,
                "target_status": r.target_status.value,
                "candles_monitored": r.candles_monitored,
                "reached_at": r.reached_at,
                "invalidated_at": r.invalidated_at,
                "expiry_at": r.expiry_at,
                "mfe": str(r.max_favorable_excursion),
                "mae": str(r.max_adverse_excursion),
                "cost": str(r.cost_impact),
                "transitions": [t.to_dict() for t in r.state_transitions],
            }
            for r in result.setup_results
        ],
    }


def test_iter_run_matches_run_exactly():
    candles = _candles()
    direct = BacktestEngine(config=BacktestConfig()).run(candles)

    events = list(BacktestEngine(config=BacktestConfig()).iter_run(candles))
    done = events[-1]
    assert done["type"] == "done"
    streamed = done["result"]

    assert _snapshot(streamed) == _snapshot(direct)
    assert streamed.duration_ms is not None


def test_one_event_per_candle_and_contiguous_sequence():
    candles = _candles()
    events = list(BacktestEngine(config=BacktestConfig()).iter_run(candles))
    candle_events = [e for e in events if e["type"] == "candle"]

    assert len(candle_events) == len(candles)
    assert [e["seq"] for e in candle_events] == list(range(len(candles)))
    assert [e["index"] for e in candle_events] == list(range(len(candles)))
    for event, candle in zip(candle_events, candles, strict=True):
        assert event["candle"] == candle.to_dict()
        assert event["progress"]["index"] == event["index"] + 1
        assert event["progress"]["total"] == len(candles)
    assert events[-1]["seq"] == len(candles)


def test_stream_never_completes_a_setup_on_its_activation_candle():
    candles = _candles()
    events = list(
        BacktestEngine(
            config=BacktestConfig(target_projection="identity")
        ).iter_run(candles)
    )
    for event in events:
        if event["type"] != "candle":
            continue
        for change in event["state_changes"]:
            setup = change["setup"]
            if change["previous_status"] != SetupStatus.ACTIVE.value:
                continue
            assert change["timestamp"] >= setup["activated_at"]
            if setup["final_status"] == SetupStatus.TARGET_REACHED.value:
                assert change["timestamp"] > setup["activated_at"]
                assert change["candle_index"] > setup["state_transitions"][0]["candle_index"]


def test_live_metrics_are_a_prefix_of_the_final_metrics():
    candles = _candles()
    events = list(BacktestEngine(config=BacktestConfig()).iter_run(candles))
    final = events[-1]["metrics"]
    last_candle = events[-2]["metrics"]
    assert last_candle == final

    first = events[0]["metrics"]
    assert first["total_setups"] == 0
    assert first["target_hit_rate_pct"] == 0.0


def test_include_live_metrics_can_be_disabled():
    candles = _candles()
    events = list(
        BacktestEngine(config=BacktestConfig()).iter_run(
            candles, include_live_metrics=False
        )
    )
    assert all(e["metrics"] is None for e in events if e["type"] == "candle")
    assert events[-1]["metrics"]["total_setups"] >= 0


def test_direction_filter_is_applied_by_the_engine():
    candles = _candles()
    both = BacktestEngine(config=BacktestConfig()).run(candles)
    longs = BacktestEngine(config=BacktestConfig(direction="long")).run(candles)
    shorts = BacktestEngine(config=BacktestConfig(direction="short")).run(candles)

    assert longs.total_setups + shorts.total_setups == both.total_setups
    assert all(r.setup.direction.value == "long" for r in longs.setup_results)
    assert all(r.setup.direction.value == "short" for r in shorts.setup_results)
