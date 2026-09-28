# Mathematical Trading Bot

A professional-grade Python **research and backtesting** framework for a
mathematical trading strategy. **This project does not perform live trading,
order execution, or exchange connectivity of any kind.**

## What it does

1. Loads historical OHLCV data from CSV files (strict validation, no silent repair).
2. Detects swing highs/lows chronologically (configurable confirmation windows).
3. Produces A/B/C setup candidates with a **replaceable, configurable reference detector**.
4. Calculates the **confirmed** mathematical target for every setup:

   $$\text{TARGET} = \frac{B + C}{A}$$

   Example: A=100, B=150, C=125 → B+C=275 → **TARGET = 2.75**.
5. Tracks each setup candle-by-candle with **no look-ahead bias**: evaluates
   the target, applies invalidation rules, records every state transition.
6. Computes statistics (hit rates, durations, per-direction, MFE/MAE).
7. Exports JSON / CSV / Markdown reports under `reports/` and research charts
   under `charts/`.
8. Exposes everything through a CLI.

> **Strategy boundary (important):** only the formula `TARGET = (B + C) / A`
> is confirmed. How A, B and C are identified in market data, how the
> mathematical target maps to a price level, and when a setup is invalidated
> are **documented, configurable interpretations** — see
> [docs/strategy.md](docs/strategy.md) and [docs/assumptions.md](docs/assumptions.md).

## Installation

Python 3.10+ required.

```bash
pip install -e .
# development / testing
pip install -e ".[dev]"
```

Optional environment overrides: copy `.env.example` to `.env` and edit.
Never store real API keys or secrets — this project has no exchange access.

## CLI usage

```bash
python -m tradingbot --help
python -m tradingbot calculate --a 100 --b 150 --c 125
python -m tradingbot validate-data --file data/sample/sample.csv
python -m tradingbot detect --file data/sample/sample_sinus_1h.csv
python -m tradingbot backtest --file data/sample/sample_sinus_1h.csv
python -m tradingbot report --file data/sample/sample_sinus_1h.csv
```

`calculate` prints the canonical example exactly:

```
A      = 100
B      = 150
C      = 125
B + C  = 275
TARGET = 2.75
```

Common backtest options (also on `detect`/`report`):

| Flag | Meaning | Default |
|---|---|---|
| `--target-mode` | `high_low_reach` or `close_reach` | `high_low_reach` |
| `--target-projection` | `c_anchored_ratio` or `identity` | `c_anchored_ratio` |
| `--invalidation` | `reference` or `none` | `reference` |
| `--left-window` / `--right-window` / `--min-separation` | swing sensitivity | 3 / 3 / 1 |
| `--min-distance` | min price distance between A→B, B→C | 0 |
| `--max-candles-active` | setup expiry (candles) | 200 |
| `--direction` | `both` / `long` / `short` (detect only) | `both` |

## Historical data format

CSV with the header `timestamp,open,high,low,close,volume`.
Timestamps are Unix epoch **milliseconds**. See
[docs/data-format.md](docs/data-format.md) for validation rules.

Two deterministic sample datasets ship with the repo:

* `data/sample/sample.csv` — the Phase 0 five-candle fixture.
* `data/sample/sample_sinus_1h.csv` — 300 one-hour candles (regenerate with
  `python scripts/generate_sample_data.py`).

## Backtesting

The engine processes candles strictly chronologically and may only use data
up to the current candle. Setups activate on the candle **after** C is
confirmed, so the activation candle itself can never count as a target reach.
Multiple and overlapping setups are supported; duplicates are suppressed.
See [docs/backtesting.md](docs/backtesting.md).

**Mathematical target success ≠ profitability.** The optional cost model
(fees/slippage/spread, default zero) only produces an informational cost
estimate; there is no execution simulation and no equity curve.

## Reports & charts

`python -m tradingbot report ...` writes `reports/backtest.json`,
`reports/backtest.csv`, `reports/backtest.md` and `charts/backtest.png`.
Reports include dataset info, configuration, detector parameters, evaluator
and invalidation interpretations, assumptions, per-setup outcomes, metrics,
warnings and errors — all derived from actual run data.

## Testing

```bash
python -m pytest tests/ -v                 # full suite
python -m pytest tests/ -q --cov=src/tradingbot   # with coverage
```

The suite covers the formula (including the mandatory 100/150/125 case),
candle validation, swing confirmation & no-look-ahead proofs, ABC validation,
target evaluation, invalidation, data validation, backtest behaviour,
metrics, reports, charts, the CLI, and a full end-to-end integration test.

## Limitations

* Research and backtesting only — **no live trading, no order execution,
  no exchange login** (by design; see the restrictions in the docs).
* A/B/C detection is a documented reference interpretation, not the
  (unspecified) original rule. Replace `ReferenceABCDetector` when the exact
  rules are defined.
* The projection from the dimensionless mathematical target to a price level
  is an interpretation (`c_anchored_ratio` by default).
* Cost model output is informational; it does not constitute a P&L simulation.

## Documentation

* [docs/architecture.md](docs/architecture.md) — components and data flow
* [docs/strategy.md](docs/strategy.md) — confirmed vs. assumed strategy rules
* [docs/backtesting.md](docs/backtesting.md) — engine semantics and guarantees
* [docs/configuration.md](docs/configuration.md) — every option explained
* [docs/data-format.md](docs/data-format.md) — CSV schema and validation
* [docs/assumptions.md](docs/assumptions.md) — full assumptions register
