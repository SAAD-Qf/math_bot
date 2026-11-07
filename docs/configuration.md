# Configuration Guide

There are two layers, each with a single source of truth:

* **A run's strategy/backtest parameters** live in
  `tradingbot.backtesting.backtest_engine.BacktestConfig`. They come from CLI
  flags or from the dashboard form (which the web layer validates with Pydantic).
* **Process-level settings** (environment label and logging) live in
  `tradingbot.config.Config` / `LoggingConfig` and can come from `.env`.

Detection, projection and invalidation values are **reference interpretations**
(see `docs/strategy.md`); only `TARGET = (B + C) / A` is confirmed.

## Swing detection (sensitivity)

| CLI flag | Default | Meaning |
|---|---|---|
| `--left-window` | 3 | candles to the left that must be less extreme |
| `--right-window` | 3 | candles to the right required to **confirm** a swing |
| `--min-separation` | 1 | min candles between same-role swings |

Higher windows → fewer, more significant swings (slower confirmation).

## A/B/C detection (reference interpretation)

| CLI flag | Default | Meaning |
|---|---|---|
| `--min-distance` | 0.0 | min price distance A→B and B→C |
| `--direction` | both | restrict detection (`both`/`long`/`short`) |

## Target evaluation

| CLI flag | Default | Meaning |
|---|---|---|
| `--target-mode` | `high_low_reach` | `high_low_reach` or `close_reach` |
| `--target-projection` | `c_anchored_ratio` | `c_anchored_ratio` or `identity` |

## Invalidation

| CLI flag | Default | Meaning |
|---|---|---|
| `--invalidation` | `reference` | `reference` (break through C) or `none` |
| `--max-candles-active` | 200 | candles before a setup expires |

## Costs (informational only)

| CLI flag | Default | Meaning |
|---|---|---|
| `--fee` | 0.0 | fee rate (fraction of notional) |
| `--slippage` | 0.0 | slippage rate |
| `--spread` | 0.0 | spread rate |

Defaults are zero. Costs never influence mathematical target outcomes.

## Engine behaviour

| CLI flag | Default | Meaning |
|---|---|---|
| `--allow-overlapping` / `--no-allow-overlapping` | true | allow concurrent same-direction setups |
| `--max-active-setups` | 1000 | safety cap on concurrent setups |
| `--allow-same-candle-activation` | false | opt in to evaluating the activation candle |
| `--allow-duplicates` | false | drop duplicate timestamps with a warning instead of failing |

## Output paths

| CLI flag | Default | Meaning |
|---|---|---|
| `--reports-dir` | `reports` | JSON/CSV/Markdown report directory (`report`) |
| `--charts-dir` | `charts` | PNG chart directory (`report`, `backtest`) |

## Logging / environment

| Env var | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | development | environment label (development/testing/production) |
| `LOG_LEVEL` | INFO | logging threshold |
| `LOG_FILE` | (stdout) | optional log file (rotating) |
| `LOG_MAX_SIZE` / `LOG_BACKUP_COUNT` | 10MB / 5 | rotation settings |
| `TRADINGBOT_DATA_DIR` | `data/sample` | dashboard dataset directory |
| `TRADINGBOT_RUNS_DIR` | `reports/web` | dashboard artifact directory |

## Programmatic usage

```python
from tradingbot import BacktestConfig, BacktestEngine
from tradingbot.data.csv_data_provider import CSVDataProvider

provider = CSVDataProvider("data/sample/sample_sinus_1h.csv")
engine = BacktestEngine(config=BacktestConfig(
    target_mode="close_reach",
    target_projection="identity",
    invalidation_rule="reference",
    max_candles_active=100,
    allow_overlapping=False,
    fee=0.001,            # informational only
))
result = engine.run(provider.get_candles())
print(result.metrics["target_hit_rate_pct"])
```
