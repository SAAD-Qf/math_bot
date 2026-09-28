"""
Historical backtesting engine.

ANTI LOOK-AHEAD DESIGN:
The engine processes candles strictly one at a time. At candle i it may only
use candles[0..i]. Setups created at candle i are activated no earlier than
candle i+1 (the "no same-candle activation" rule), so the activation candle's
own extreme can never be counted as a target reach. Invalidation and target
checks also start at the next candle after activation.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..domain import (
    ABCSetup,
    BacktestResult,
    Candle,
    SetupResult,
    StateTransition,
)
from ..domain.enums import (
    InvalidationStatus,
    SetupDirection,
    SetupStatus,
    TargetStatus,
)
from ..exceptions import BacktestError
from ..strategy.cost_model import CostModel, build_cost_model
from ..strategy.invalidation import InvalidationRule, build_invalidation_rule
from ..strategy.mathematical_strategy import MathematicalStrategy
from ..strategy.target_evaluator import TargetEvaluator, build_target_evaluator
from ..strategy.target_projection import build_target_projector

ZERO = Decimal('0')
ONE = Decimal('1')


@dataclass
class BacktestConfig:
    """Backtest engine configuration.

    Attributes:
        target_mode: HIGH_LOW_REACH or CLOSE_REACH (interpretation, see docs).
        invalidation_rule: "reference" or "none".
        max_candles_active: candles a setup may remain active before expiry.
        allow_overlapping: whether new setups may activate while same-direction
            setups are still active. If False, a new setup is skipped while
            another same-direction setup is active.
        allow_same_candle_activation: If True (default False), a setup detected
            at candle i may be evaluated against candle i itself. Keep False to
            make look-ahead structurally impossible.
        fee/slippage/spread: optional cost model rates (informational only).
        target_projection: how the dimensionless mathematical target maps to a
            price level: "c_anchored_ratio" (reference interpretation) or
            "identity".
        max_active_setups: safety cap on concurrently active setups.
    """
    target_mode: Any = "high_low_reach"
    invalidation_rule: str = "reference"
    max_candles_active: int = 200
    allow_overlapping: bool = True
    allow_same_candle_activation: bool = False
    fee: float = 0.0
    slippage: float = 0.0
    spread: float = 0.0
    target_projection: str = "c_anchored_ratio"
    max_active_setups: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_mode": str(self.target_mode),
            "invalidation_rule": str(self.invalidation_rule),
            "max_candles_active": self.max_candles_active,
            "allow_overlapping": self.allow_overlapping,
            "allow_same_candle_activation": self.allow_same_candle_activation,
            "fee": self.fee,
            "slippage": self.slippage,
            "spread": self.spread,
            "target_projection": self.target_projection,
            "max_active_setups": self.max_active_setups,
        }


class BacktestEngine:
    """Runs a MathematicalStrategy over historical candles chronologically.

    Supports multiple and overlapping setups, enforces duplicate prevention,
    valid state transitions and no look-ahead bias.
    """

    def __init__(
        self,
        strategy: Optional[MathematicalStrategy] = None,
        config: Optional[BacktestConfig] = None,
        target_evaluator: Optional[TargetEvaluator] = None,
        invalidation_rule: Optional[InvalidationRule] = None,
        cost_model: Optional[CostModel] = None,
    ):
        self.strategy = strategy or MathematicalStrategy(
            projector=build_target_projector(
                (config or BacktestConfig()).target_projection
            )
        )
        self.config = config or BacktestConfig()
        self.target_evaluator = target_evaluator or build_target_evaluator(
            self._resolve_target_mode(self.config.target_mode)
        )
        self.invalidation_rule = invalidation_rule or build_invalidation_rule(
            self.config.invalidation_rule,
            max_candles_active=self.config.max_candles_active,
        )
        self.cost_model = cost_model or build_cost_model(
            fee=Decimal(str(self.config.fee)),
            slippage=Decimal(str(self.config.slippage)),
            spread=Decimal(str(self.config.spread)),
        )

    @staticmethod
    def _resolve_target_mode(mode: Any):
        from ..domain.enums import TargetEvaluationMode

        if isinstance(mode, TargetEvaluationMode):
            return mode
        return TargetEvaluationMode(str(mode).lower())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, candles: List[Candle]) -> BacktestResult:
        """Run the backtest over a chronological candle list.

        Raises:
            BacktestError: on invalid input data.
        """
        import time

        if not candles:
            raise BacktestError("No candles provided to backtest")

        # 1. Validate chronological order (no look-ahead is possible otherwise).
        timestamps = [c.timestamp for c in candles]
        if any(timestamps[i] > timestamps[i + 1] for i in range(len(timestamps) - 1)):
            raise BacktestError(
                "Candles must be sorted chronologically (ascending timestamps)"
            )

        start_time = time.monotonic()
        self.strategy.reset()

        setup_results: List[SetupResult] = []
        active: List[SetupResult] = []
        warnings: List[str] = []
        errors: List[str] = []

        for i, candle in enumerate(candles):
            # --- 1. Update active setups with the CURRENT candle ------------
            still_active: List[SetupResult] = []
            for result in active:
                self._evaluate_active_setup(result, candle, i)
                if result.is_terminal():
                    setup_results.append(result)
                else:
                    still_active.append(result)
            active = still_active

            # --- 2. Feed the candle to the detector --------------------------
            new_setups = self.strategy.feed(candle)

            for setup in new_setups:
                # Duplicate prevention at engine level: a (direction, C value,
                # C timestamp) tuple can only be activated once.
                key = (
                    setup.direction.value,
                    str(setup.c.value),
                    setup.c.timestamp,
                )
                if any(
                    (r.setup.direction.value, str(r.setup.c.value), r.setup.c.timestamp) == key
                    for r in setup_results
                ) or any(
                    (r.setup.direction.value, str(r.setup.c.value), r.setup.c.timestamp) == key
                    for r in active
                ):
                    warnings.append(
                        f"Candle {i}: duplicate setup suppressed "
                        f"({key[0]} C={key[1]}@{key[2]})"
                    )
                # Overlap policy (engine-level, mirrors detector policy).
                elif not self.config.allow_overlapping and any(
                    r.setup.direction == setup.direction for r in active
                ):
                    warnings.append(
                        f"Candle {i}: setup skipped due to overlap policy "
                        f"({setup.direction.value})"
                    )
                elif len(active) >= self.config.max_active_setups:
                    warnings.append(f"Candle {i}: max_active_setups reached; setup skipped")
                else:
                    result = self._activate(setup, candle, i)
                    active.append(result)

        # Remaining active setups at the end of data: still ACTIVE (not counted
        # as terminal outcomes); include them for transparency.
        setup_results.extend(active)

        duration_ms = int((time.monotonic() - start_time) * 1000)

        from ..backtesting.metrics import compute_metrics

        metrics = compute_metrics(setup_results, candles)

        assumptions = {
            "formula": "TARGET = (B + C) / A (confirmed)",
            "abc_detection": "CONFIGURABLE REFERENCE interpretation (not confirmed)",
            "target_evaluation": self.target_evaluator.describe(),
            "invalidation": self.invalidation_rule.describe(),
            "cost_model": self.cost_model.describe(),
            "activation_rule": (
                "Setups activate on the candle AFTER C-confirmation "
                "(no same-candle evaluation by default)."
            ),
        }

        return BacktestResult(
            dataset={
                "candle_count": len(candles),
                "first_timestamp": candles[0].timestamp,
                "last_timestamp": candles[-1].timestamp,
            },
            config=self._config_report(),
            setup_results=setup_results,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
            assumptions=assumptions,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Setup lifecycle
    # ------------------------------------------------------------------
    def _activate(self, setup: ABCSetup, activation_candle: Candle, index: int) -> SetupResult:
        """Activate a newly created setup and record the transition."""
        result = SetupResult(
            setup=setup,
            activated_at=activation_candle.timestamp,
            final_status=SetupStatus.ACTIVE,
            target_status=TargetStatus.PENDING,
            invalidation_status=InvalidationStatus.NONE,
            target=setup.target,
        )
        result.state_transitions.append(
            StateTransition(
                timestamp=activation_candle.timestamp,
                previous_state=SetupStatus.PENDING,
                new_state=SetupStatus.ACTIVE,
                reason="Setup activated on candle after C-confirmation",
                candle_index=index,
            )
        )
        return result

    def _evaluate_active_setup(
        self, result: SetupResult, candle: Candle, index: int
    ) -> None:
        """Evaluate one candle against one active setup (mutates result)."""
        setup = result.setup
        result.candles_monitored += 1

        # Track MFE / MAE (price excursion fractions relative to C point).
        c_value = setup.c.value
        if c_value > 0:
            if setup.direction == SetupDirection.LONG:
                favorable = (candle.high - c_value) / c_value
                adverse = (c_value - candle.low) / c_value
            else:
                favorable = (c_value - candle.low) / c_value
                adverse = (candle.high - c_value) / c_value
            result.max_favorable_excursion = max(
                result.max_favorable_excursion, favorable
            )
            result.max_adverse_excursion = max(
                result.max_adverse_excursion, adverse
            )

        # 1) Target check FIRST (target has priority over invalidation when both
        #    occur on the same candle). The projected PRICE target is evaluated
        #    against candles; the mathematical target (B+C)/A is preserved on
        #    the setup and in reports.
        price_target = Decimal(str(setup.metadata["price_target"]))
        target_reached = self.target_evaluator.evaluate(
            price_target, setup.direction, candle
        )
        if target_reached:
            self._transition(
                result,
                timestamp=candle.timestamp,
                new_status=SetupStatus.TARGET_REACHED,
                target_status=TargetStatus.REACHED,
                invalidation_status=InvalidationStatus.NONE,
                reason=(
                    f"Price target {price_target} reached "
                    f"({self.target_evaluator.mode.value}); "
                    f"mathematical target={result.target}"
                ),
                candle_index=index,
            )
            result.reached_at = candle.timestamp
            result.completed_at = candle.timestamp
            self._record_outcome(result, candle)
            return

        # 2) Invalidation / expiry check.
        invalidation = self.invalidation_rule.check(
            setup, candle, result.candles_monitored
        )
        if invalidation == InvalidationStatus.INVALIDATED:
            self._transition(
                result,
                timestamp=candle.timestamp,
                new_status=SetupStatus.INVALIDATED,
                target_status=TargetStatus.NOT_REACHED,
                invalidation_status=InvalidationStatus.INVALIDATED,
                reason="Invalidation rule triggered",
                candle_index=index,
            )
            result.invalidated_at = candle.timestamp
            result.completed_at = candle.timestamp
            self._record_outcome(result, candle)
        elif invalidation == InvalidationStatus.EXPIRED:
            self._transition(
                result,
                timestamp=candle.timestamp,
                new_status=SetupStatus.EXPIRED,
                target_status=TargetStatus.NOT_REACHED,
                invalidation_status=InvalidationStatus.EXPIRED,
                reason=f"Setup expired after {result.candles_monitored} active candles",
                candle_index=index,
            )
            result.expiry_at = candle.timestamp
            result.completed_at = candle.timestamp
            self._record_outcome(result, candle)

    def _record_outcome(self, result: SetupResult, candle: Candle) -> None:
        """Record the informational gross outcome and cost estimate."""
        setup = result.setup
        c_value = setup.c.value
        if c_value > 0 and result.completed_at is not None:
            if setup.direction == SetupDirection.LONG:
                result.gross_outcome = (candle.close - c_value) / c_value
            else:
                result.gross_outcome = (c_value - candle.close) / c_value
        notional = price_level if (price_level := setup.metadata.get("price_target")) else ONE
        result.cost_impact = self.cost_model.estimate_cost(Decimal(str(notional)))

    def _transition(
        self,
        result: SetupResult,
        timestamp: int,
        new_status: SetupStatus,
        target_status: TargetStatus,
        invalidation_status: InvalidationStatus,
        reason: str,
        candle_index: Optional[int] = None,
    ) -> None:
        """Apply a validated state transition and record it."""
        previous = result.final_status
        if previous == new_status:
            return
        valid_transitions = {
            SetupStatus.ACTIVE: {
                SetupStatus.TARGET_REACHED, SetupStatus.INVALIDATED, SetupStatus.EXPIRED
            },
            SetupStatus.PENDING: {SetupStatus.ACTIVE},
            SetupStatus.TARGET_REACHED: set(),
            SetupStatus.INVALIDATED: set(),
            SetupStatus.EXPIRED: set(),
        }
        if new_status not in valid_transitions.get(previous, set()):
            raise BacktestError(
                f"Invalid state transition {previous} -> {new_status}"
            )
        result.final_status = new_status
        result.target_status = target_status
        result.invalidation_status = invalidation_status
        result.state_transitions.append(
            StateTransition(
                timestamp=timestamp,
                previous_state=previous,
                new_state=new_status,
                reason=reason,
                candle_index=candle_index,
            )
        )

    def _config_report(self) -> Dict[str, Any]:
        cfg = self.config.to_dict()
        cfg["strategy"] = self.strategy.describe()
        cfg["cost_model"] = self.cost_model.describe()
        return cfg
