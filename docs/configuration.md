# Configuration Guide

Every important parameter is configurable — nothing strategic is hard-coded.
Three equivalent layers exist: constructor arguments, environment variables
(`.env`, see `.env.example`), and CLI flags.

## Swing detection (sensitivity)

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `SWING_LEFT_WINDOW` | `--left-window` | 3 | candles to the left that must be less extreme |
| `SWING_RIGHT_WINDOW` | `--right-window` | 3 | candles to the right required to **confirm** a swing |
| `SWING_MIN_SEPARATION` | `--min-separation` | 1 | min candles between same-role swings |

Higher windows → fewer, more significant swings (slower confirmation).

## A/B/C detection (reference interpretation)

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `MIN_DISTANCE` | `--min-distance` | 0.0 | min price distance A→B and B→C |
| `DIRECTION` | `--direction` | both | restrict detection (`both`/`long`/`short`, detect command) |

## Target evaluation

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `TARGET_MODE` | `--target-mode` | `high_low_reach` | `high_low_reach` or `close_reach` |
| `TARGET_PROJECTION` | `--target-projection` | `c_anchored_ratio` | `c_anchored_ratio` or `identity` |

## Invalidation

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `INVALIDATION_RULE` | `--invalidation` | `reference` | `reference` (break through C) or `none` |
| `MAX_CANDLES_ACTIVE` | `--max-candles-active` | 200 | candles before a setup expires |

## Costs (informational only)

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `TRANSACTION_COST` | — | 0.0 | fee rate (fraction of notional) |
| `SLIPPAGE` | — | 0.0 | slippage rate |
| `SPREAD` | — | 0.0 | spread rate |

Defaults are zero. Costs never influence mathematical target outcomes.

## Engine behaviour

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `ALLOW_OVERLAPPING` | — | true | allow concurrent same-direction setups |

## Output paths

| Env var | CLI flag | Default | Meaning |
|---|---|---|---|
| `REPORTS_DIR` | `--reports-dir` | `reports` | JSON/CSV/Markdown report directory |
| `CHARTS_DIR` | `--charts-dir` | `charts` | PNG chart directory |

## Logging

| Env var | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | INFO | logging threshold |
| `LOG_FILE` | (stdout) | optional log file (rotating) |
| `LOG_MAX_SIZE` / `LOG_BACKUP_COUNT` | 10MB / 5 | rotation settings |

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
