# Architecture

## Overview

The system is a layered research/backtesting pipeline with strict separation
of concerns. The strategy core knows nothing about CSV files, exchanges, the
CLI, or report formatting.

```
CSV files ──► data layer ──► backtest engine ──► metrics
                                 ▲                  │
                  detection layer│                  ▼
                  (swings, A/B/C)│           reporting layer
                                 │           (JSON/CSV/MD, charts)
                  strategy layer ┘
                  (pipeline, target, invalidation, costs)
```

## Layers

### Domain (`src/tradingbot/domain/`)

Strongly typed, validated models shared by every layer:

* `Candle` — OHLCV with full validation (finite, non-negative, low ≤ open/close ≤ high).
* `PricePoint` — value + timestamp + candle_index + role + metadata.
* `ABCSetup` — A/B/C points, direction, lifecycle and target statuses,
  chronological validation (A ≤ B ≤ C timestamps, strictly increasing indices).
* `SetupResult`, `BacktestResult`, `StateTransition` — outcome records and
  auditable lifecycle transitions.
* Enums: `SetupDirection`, `SetupStatus`, `TargetStatus`,
  `InvalidationStatus`, `TargetEvaluationMode`, `PointRole`.

### Mathematical engine (`src/tradingbot/mathematical_engine.py`)

Standalone, deterministic calculator for the confirmed formula
`TARGET = (B + C) / A`. Pure arithmetic and validation — no detection or
interpretation logic lives here.

### Detection (`src/tradingbot/detection/`)

* `SwingDetector` — incremental pivot detection with explicit
  point-time vs. confirmation-time semantics (the core no-look-ahead device).
* `ABCDetector` (interface) + `ReferenceABCDetector` (replaceable reference
  implementation).

### Strategy (`src/tradingbot/strategy/`)

* `Strategy` (Phase 0 ABC, preserved) and `MathematicalStrategy` — the
  pipeline: candles → swings → A/B/C → validation → `(B+C)/A` → setup creation.
* `TargetEvaluator` (`HIGH_LOW_REACH` / `CLOSE_REACH`).
* `TargetProjector` (`c_anchored_ratio` / `identity`) — the explicit,
  replaceable bridge from the dimensionless mathematical target to a price
  level.
* `InvalidationRule` (`reference` / `none`).
* `CostModel` (`zero` default; fee/slippage/spread optional, informational).

### Backtesting (`src/tradingbot/backtesting/`)

* `BacktestEngine` — chronological driver; activates, monitors and closes
  setups; records transitions; prevents duplicates and look-ahead.
* `compute_metrics` — all documented statistics from actual results.

### Data (`src/tradingbot/data/`)

* `HistoricalDataProvider` (ABC) + `CSVDataProvider` (strict validation,
  explicit errors, no silent repair) + `DataValidationReport`.

### Reporting (`src/tradingbot/reporting/`)

* `Reporter` — JSON / CSV / Markdown generation and export under `reports/`.
* `ChartGenerator` — matplotlib research charts under `charts/`
  (no equity curve: there is no execution model).

### Infrastructure

* `config.py` — dataclass configuration from environment variables.
* `logging.py` — configurable logging with rotation.
* `exceptions.py` — single `TradingBotError` hierarchy.
* `cli.py` / `__main__.py` — argparse CLI (`python -m tradingbot`).

## Key design decisions

1. **Detection ↔ math separation.** The detector produces A/B/C candidates;
   the engine only computes `(B+C)/A`. Detector assumptions can never leak
   into the formula.
2. **Two notions of time.** Swings (and therefore setups) carry
   `point_index/point_timestamp` (where the extreme occurred) and
   `confirmed_at_index/confirmed_at_timestamp` (when it became knowable).
   Availability is always gated on the latter.
3. **Replaceable assumptions.** Detector, target evaluation, projection,
   invalidation and costs are all interfaces with documented reference
   implementations.
4. **Explicit state machine.** Every setup transition is recorded with
   timestamp, previous state, new state, reason and candle index; invalid
   transitions raise.
