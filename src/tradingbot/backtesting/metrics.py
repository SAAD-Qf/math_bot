"""
Backtest metrics.

Every metric is computed from the recorded SetupResults of an actual run —
nothing is fabricated. Durations are in milliseconds of dataset time
(candle-timestamp differences), not wall-clock time.
"""

from decimal import Decimal
from typing import Any, Dict, List

from ..domain import Candle, SetupResult
from ..domain.enums import SetupDirection, SetupStatus

ZERO = Decimal('0')


def _median(values: List[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100.0, 4) if denominator else 0.0


def _avg_decimal(values: List[Decimal]) -> float:
    """Average of Decimal values as float (0.0 when empty)."""
    if not values:
        return 0.0
    return round(float(sum(values) / Decimal(len(values))), 6)


def compute_metrics(setup_results: List[SetupResult], candles: List[Candle]) -> Dict[str, Any]:
    """Compute all documented metrics for a backtest run.

    Metric definitions (all computed from actual SetupResults):
        total_setups: number of setups tracked during the run.
        valid_setups: setups that reached terminal states
            (target/invalidation/expiry) — i.e. completed evaluations.
        invalidated_setups: setups whose invalidation rule triggered.
        expired_setups: setups that hit the max-active-candle expiry.
        target_reached: setups whose mathematical target was reached.
        target_not_reached: terminal setups that did not reach the target.
        target_hit_rate: target_reached / total_setups * 100.
        invalidation_rate: invalidated_setups / total_setups * 100.
        completion_rate: terminal setups / total_setups * 100.
        avg/median/min/max duration_ms: activation -> completion dataset time.
        long/short statistics: the same outcome counts per direction.
        setup_frequency: setups per 100 candles.
        max_favorable_excursion_avg / max_adverse_excursion_avg: mean MFE/MAE
            across terminal setups (fraction of price, informational).
    """
    total = len(setup_results)
    terminal = [
        r for r in setup_results
        if r.final_status in (SetupStatus.TARGET_REACHED, SetupStatus.INVALIDATED, SetupStatus.EXPIRED)
    ]
    target_reached = [r for r in terminal if r.final_status == SetupStatus.TARGET_REACHED]
    invalidated = [r for r in terminal if r.final_status == SetupStatus.INVALIDATED]
    expired = [r for r in terminal if r.final_status == SetupStatus.EXPIRED]
    still_active = [r for r in setup_results if r not in terminal]

    durations = [
        r.duration_ms() for r in terminal if r.duration_ms() is not None
    ]

    metrics: Dict[str, Any] = {
        "total_setups": total,
        "valid_setups": len(terminal),
        "invalidated_setups": len(invalidated),
        "expired_setups": len(expired),
        "target_reached": len(target_reached),
        "target_not_reached": len(terminal) - len(target_reached),
        "target_hit_rate_pct": _pct(len(target_reached), total),
        "invalidation_rate_pct": _pct(len(invalidated), total),
        "completion_rate_pct": _pct(len(terminal), total),
        "still_active_at_end": len(still_active),
        "duration": {
            "avg_ms": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "median_ms": _median(durations),
            "min_ms": min(durations) if durations else 0,
            "max_ms": max(durations) if durations else 0,
        },
        "long": _direction_stats(setup_results, SetupDirection.LONG),
        "short": _direction_stats(setup_results, SetupDirection.SHORT),
        "setup_frequency_per_100_candles": round(
            total / len(candles) * 100.0, 4
        ) if candles else 0.0,
        "max_favorable_excursion_avg": _avg_decimal(
            [r.max_favorable_excursion for r in terminal]
        ),
        "max_adverse_excursion_avg": _avg_decimal(
            [r.max_adverse_excursion for r in terminal]
        ),
    }
    return metrics


def _direction_stats(results: List[SetupResult], direction: SetupDirection) -> Dict[str, Any]:
    subset = [r for r in results if r.setup.direction == direction]
    terminal = [
        r for r in subset
        if r.final_status in (SetupStatus.TARGET_REACHED, SetupStatus.INVALIDATED, SetupStatus.EXPIRED)
    ]
    reached = [r for r in terminal if r.final_status == SetupStatus.TARGET_REACHED]
    return {
        "total": len(subset),
        "target_reached": len(reached),
        "invalidated": len([r for r in terminal if r.final_status == SetupStatus.INVALIDATED]),
        "expired": len([r for r in terminal if r.final_status == SetupStatus.EXPIRED]),
        "target_hit_rate_pct": _pct(len(reached), len(subset)),
    }
