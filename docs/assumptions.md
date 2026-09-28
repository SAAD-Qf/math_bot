# Assumptions Register

Single source of truth for every assumption in the system. Items marked
**CONFIRMED** are established strategy facts; everything else is a
documented, replaceable interpretation.

## Confirmed

* **Formula:** `TARGET = (B + C) / A`, evaluated exactly (Decimal).
  Canonical example: A=100, B=150, C=125 → B+C=275 → TARGET=2.75.
* **Validation:** A ≠ 0 and A > 0; B > 0; C > 0; NaN/infinity/non-numeric
  rejected.
* **Scope:** research + historical backtesting only. No live trading, order
  execution, or exchange connectivity exists anywhere in the codebase.

## A/B/C detection (REFERENCE — not confirmed)

* Swings are local extremes confirmed by `right_window` subsequent candles.
* Tie rule: the first candle of a plateau is the swing point.
* LONG = low→high→low (up-wave then pullback); SHORT mirrored.
* One setup per (direction, C point index).
* All of the above is replaceable via the `ABCDetector` interface.

## Target evaluation (assumed)

* `high_low_reach`: long reaches when `high >= price_target`; short when
  `low <= price_target`.
* `close_reach`: long reaches when `close >= price_target`; short when
  `close <= price_target`.

## Target projection (assumed)

* `c_anchored_ratio` (default): long `price_target = C * TARGET`;
  short `price_target = C / TARGET`.
* `identity`: `price_target = TARGET`.

## Invalidation (assumed)

* `reference`: long invalid when `low <= C`; short invalid when `high >= C`.
* Expiry after `max_candles_active` monitored candles (both rules).

## Data handling

* Timestamps are Unix epoch milliseconds.
* Duplicate timestamps are rejected by default (`allow_duplicates` relaxes
  this with a warning).
* Unsorted rows are sorted ascending with a warning; no other repair is
  performed — corrupted values are rejected with `DataProviderError`.

## Reporting

* Every reported number is computed from actual `SetupResult` records of a
  real run; no metric is fabricated or estimated.
* Durations use dataset time (candle-timestamp differences in ms), not
  wall-clock time.

## Explicitly out of scope

* Order execution, fills, leverage, exchange APIs, API keys.
* Profitability claims: cost values are informational and do not affect
  mathematical target outcomes.
