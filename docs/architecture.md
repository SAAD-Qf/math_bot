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
                  strategy layer ┘                  │
                  (pipeline, target, invalidation, costs)
                                                     ▼
                                      web layer (optional, local)
                                      replay/SSE/polling + dashboard
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

* `BacktestEngine.iter_run()` — chronological driver yielding one event per
  candle (candle, detected setups, state changes, warnings, live metrics) and
  a final `done` event carrying the `BacktestResult`.
* `BacktestEngine.run()` — a thin aggregation over `iter_run()`, so CLI,
  reports and the browser replay use exactly one evaluation path.
* `compute_metrics` — all documented statistics from actual results.

### Web (`src/tradingbot/web/`, optional `web` extra)

* `service.RunRegistry` — the only web module touching data loading, the
  engine, reporters or charts. Holds at most 50 in-memory runs, enforces a
  20 MB upload limit and a 20,000-candle web limit, and resolves dataset names
  strictly inside `data/sample`.
* `app.create_app()` — FastAPI page/API/SSE routes, JSON error handlers and a
  local-only default bind (`127.0.0.1`).
* Templates + vanilla JS/CSS — no build step, no CDN, offline. The server
  renders truth; the browser formats events and draws a `<canvas>` chart.
* Replay controls (`start/pause/step/stop/speed`) are gated server-side;
  `GET /api/runs/{id}/state` is the deterministic polling fallback to SSE.

### Data (`src/tradingbot/data/`)

* `HistoricalDataProvider` (ABC) + `CSVDataProvider` (strict validation,
  explicit errors, no silent repair) + `DataValidationReport`.

### Reporting (`src/tradingbot/reporting/`)

* `Reporter` — JSON / CSV / Markdown generation and export under `reports/`.
* `ChartGenerator` — matplotlib research charts under `charts/`
  (no equity curve: there is no execution model).

### Infrastructure

* `config.py` — environment/logging configuration only; run parameters have a
  single source of truth in `BacktestConfig`.
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
