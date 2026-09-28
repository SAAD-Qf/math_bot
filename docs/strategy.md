# Strategy Specification — Confirmed vs. Assumed

This document separates what is **CONFIRMED** about the strategy from what is
**CONFIGURABLE / ASSUMED**. Nothing in the assumed sections may be presented
as a confirmed fact.

---

## CONFIRMED

### The formula

$$\text{TARGET} = \frac{B + C}{A}$$

* Implemented exactly in `src/tradingbot/mathematical_engine.py`
  (`MathematicalEngine.calculate_target`) and mirrored in
  `ABCSetup.calculate_target`.
* Example: A=100, B=150, C=125 → B+C=275 → **TARGET=2.75**.
* Verified by `tests/test_math_engine.py::test_formula_canonical_example`
  and by the CLI: `python -m tradingbot calculate --a 100 --b 150 --c 125`.
* The formula is never replaced by `(B*C)/A`, `(B+C)/2`, `B/A + C`, or any
  other variation; a dedicated test guards against this.

### Input validation (mathematical engine)

* A cannot be zero (division by zero).
* A must be positive (strict mode, default).
* B must be positive; C must be positive.
* NaN, ±infinity, and non-numeric inputs are rejected.
* Arithmetic uses `Decimal` with a configurable precision context
  (28 significant digits by default).

---

## CONFIGURABLE / ASSUMED

### 1. A/B/C detection — `ReferenceABCDetector` (assumption)

The exact original rules for identifying A, B and C in market candles are
**NOT confirmed**. The repository ships a deterministic, configurable
*reference* detector so the system is runnable and testable:

* Swing highs/lows are found with `SwingDetector` (configurable
  `left_window`, `right_window`, `min_separation`).
* LONG: A = swing low, B = swing high after A, C = swing low after B
  (an up-wave, then a pullback). SHORT: mirrored.
* A setup is emitted only when C is *confirmed* (see docs/backtesting.md).
* Constraints: strictly increasing A→B→C point indices, optional
  `min_distance`, one setup per (direction, C point index).

**Replace, do not trust.** Implement the `ABCDetector` interface and inject
it into `MathematicalStrategy` to use the exact rules once defined. The
mathematical engine, evaluation and backtesting remain unchanged.

### 2. Target evaluation (interpretation)

The formula yields a value; how that value is checked against candles is an
interpretation with two configurable modes:

* `HIGH_LOW_REACH` — long: `candle.high >= price_target`;
  short: `candle.low <= price_target` (intrabar extreme touch counts).
* `CLOSE_REACH` — long: `candle.close >= price_target`;
  short: `candle.close <= price_target` (closes only).

### 3. Target projection (interpretation)

`TARGET = (B + C) / A` is dimensionless when A shares B and C's price units,
while candles trade in price units. A projection rule is therefore required
and is configurable:

* `c_anchored_ratio` (default) — long: `price_target = C * TARGET`;
  short: `price_target = C / TARGET`. C anchors the projection.
* `identity` — `price_target = TARGET` (only meaningful when the instrument's
  price scale equals the mathematical value scale).

The mathematical target is always preserved untouched on the setup
(`setup.target`) and in reports; only the *projected* price target is
compared against candles.

### 4. Invalidation (interpretation)

* `reference` rule — long invalidated when `candle.low <= C`;
  short invalidated when `candle.high >= C`; setups expire after
  `max_candles_active` monitored candles.
* `none` rule — no price-based invalidation; expiry only.

### 5. Execution assumptions

* No execution exists. "Reached" means the price condition was observed, not
  that an order filled.
* Cost model output (fees/slippage/spread) is informational only and never
  influences whether a mathematical target is reached.
* No equity curve is produced because there is no execution model.
