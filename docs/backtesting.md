# Backtesting Specification

## Overview

`BacktestEngine` runs `MathematicalStrategy` over historical candles in
strict chronological order and records per-setup outcomes plus aggregate
metrics. It simulates **evaluation only** — there is no order execution.

## Processing model

For each candle `i` (ascending timestamps enforced):

1. **Update active setups** with candle `i`:
   * target evaluation (price target vs. candle high/low or close),
   * invalidation / expiry check,
   * MFE/MAE tracking,
   * terminal transitions recorded (`StateTransition` audit trail).
2. **Feed candle `i` to the detector.** Any newly created setup is a
   *candidate* for activation.

## Guarantees

### No look-ahead bias

* The engine may only use `candles[0..i]` at step `i`; unsorted input raises
  `BacktestError`.
* Swings are only available after their right-window confirmation
  (`confirmed_at_index`); setups only appear when C is confirmed.
* **No same-candle activation:** a setup created at candle `i` is activated
  and first evaluated at candle `i+1` or later
  (`allow_same_candle_activation=False` by default), so the activation
  candle's own extreme can never complete the setup.
* Target checks and invalidation checks read only the current candle and
  setup state; nothing reads forward.

### Duplicate prevention

One setup per `(direction, C value, C timestamp)` tuple; the engine also
suppresses duplicates with a warning if a detector emits an identical key.

### Valid state machine

```
PENDING ──► ACTIVE ──► TARGET_REACHED | INVALIDATED | EXPIRED
```

`_transition` validates every move and raises `BacktestError` on invalid
transitions; terminal states have no outgoing edges. Every applied
transition records timestamp, previous state, new state, reason and candle
index.

### Multiple & overlapping setups

Any number of setups may be active concurrently (`max_active_setups` caps
runaway growth). With `allow_overlapping=False`, a new setup is skipped
while a same-direction setup is active (recorded as a warning).

## Evaluation order within a candle

Target first: if both the target and invalidation conditions occur on the
same candle, the setup counts as **target reached** (documented tie-break).

## Semantics of "reached"

The mathematical target `TARGET = (B + C) / A` (confirmed) is evaluated via
its projected **price target** (interpretation, see docs/strategy.md §3)
using the selected `TargetEvaluator` mode. The mathematical value is always
preserved untouched on the setup and in reports.

## Outcome statuses

| Status | Meaning |
|---|---|
| `TARGET_REACHED` | price target condition observed (after activation) |
| `INVALIDATED` | invalidation rule triggered (reference: price through C) |
| `EXPIRED` | setup exceeded `max_candles_active` monitored candles |
| `ACTIVE` | still open when the dataset ends (not a terminal outcome; excluded from completion/hit-rate rates) |

## Metrics

All metrics derive from recorded `SetupResult`s (see
`src/tradingbot/backtesting/metrics.py` for exact definitions): totals,
per-status counts, hit/invalidation/completion rates, duration
(avg/median/min/max in dataset-ms), per-direction breakdowns, setup
frequency, and average MFE/MAE. Nothing is fabricated.

## Costs

`fee`, `slippage`, `spread` (all default 0) feed an informational cost
estimate per completed setup. They never change target or invalidation
outcomes, and there is no P&L/equity simulation.
