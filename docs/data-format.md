# Data Format & Validation

## Required CSV schema

```csv
timestamp,open,high,low,close,volume
1609459200000,100.0,105.0,95.0,102.0,1000.0
1609462800000,102.0,108.0,100.0,106.0,1200.0
```

* **timestamp** — Unix epoch **milliseconds** (integer). ISO strings are
  rejected.
* **open/high/low/close** — decimal numbers; `low <= open,close <= high`.
* **volume** — non-negative decimal.
* Additional columns are ignored; column order does not matter; a UTF-8 BOM
  is tolerated.

## Validation rules (strict — no silent repair)

Every violation raises `DataProviderError` with the row number and reason:

| Check | Error message contains |
|---|---|
| missing required columns | `missing required columns` |
| empty file / no data rows | `empty` / `no data rows` |
| malformed numbers (`abc`) | `not a valid number` |
| `NaN` / empty / `null` values | `NaN` / `missing` |
| ±infinity values | `infinite` |
| missing timestamp / non-integer timestamp | `timestamp` |
| duplicate timestamps | `duplicate timestamp` |
| invalid OHLC relationships | `Invalid` / `inconsistent` |
| negative prices or volume | `negative` |

## Duplicates and ordering

* Duplicate timestamps **fail** by default. With
  `config={"allow_duplicates": True}` (or CLI `--allow-duplicates` on
  `validate-data`), duplicates are dropped and reported as warnings.
* Rows not in ascending timestamp order are **sorted** with a warning —
  the only "repair" performed, and always reported.

## Loading data programmatically

```python
from tradingbot.data.csv_data_provider import CSVDataProvider

provider = CSVDataProvider("my_dataset.csv")
report = provider.validate()          # DataValidationReport
assert report.is_valid
candles = provider.get_candles()      # optional start/end ms filtering
```

`DataValidationReport.to_dict()` (embedded in reports) contains row/candle
counts, duplicate statistics, sort status, warnings and errors.

## Sample datasets

* `data/sample/sample.csv` — Phase 0 five-candle fixture (used by unit tests).
* `data/sample/sample_sinus_1h.csv` — 300 deterministic one-hour candles.
  Regenerate: `python scripts/generate_sample_data.py [path] [count]`.
  The generator is a pure function of constants (no RNG) — running it twice
  yields identical files.

## Using another dataset

Any CSV matching the schema above works with **zero code changes**:

```bash
python -m tradingbot validate-data --file path/to/your.csv
python -m tradingbot backtest --file path/to/your.csv
```
