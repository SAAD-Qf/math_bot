# Agent Notes

Resume context for AI agents working on this repository.

## Read first

* `TODO.md` — ordered list of incomplete work; **the source of truth for what
  to do next**. Phase 1 is the browser UI.
* `.freebuff/memory/` — local session logs (latest: `session-2026-11-07.md`) with
  environment facts, verified baseline, and open questions. This directory is
  git-excluded (`.git/info/exclude`), so it exists only in this working copy;
  `TODO.md` is the tracked summary.

## Project in one paragraph

A Python **research/backtesting** framework for `TARGET = (B + C) / A`. Loads
strictly validated OHLCV CSVs, detects swing-based A/B/C setups, evaluates the
target candle-by-candle with no look-ahead bias, and exports JSON/CSV/Markdown
reports plus matplotlib charts. **No live trading, no order execution, no
exchange connectivity, no API keys — keep it that way.**

## Environment

* Windows; run commands with **bash** syntax (Git Bash).
* Use the local venv: `.venv/Scripts/python.exe` (Python 3.15.2).
  There is no `pip` on PATH — use `python -m pip`.
* Install: `.venv/Scripts/python.exe -m pip install -e ".[dev]"`.

## Checks

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
.venv/Scripts/ruff.exe check src tests scripts
.venv/Scripts/mypy.exe src
```

Baseline: 151 tests pass, ruff/mypy clean, coverage 84.8%. Do not regress these.

## Conventions

* Immutable dataclasses in `domain/`; Decimal for prices, never float in core math.
* Business logic stays out of `cli.py`; reporters/charts consume result dicts.
* Keep the no-look-ahead guarantees documented in `docs/backtesting.md` intact:
  setups activate no earlier than the candle after C is confirmed.
* Detection and price projection are documented **interpretations**, not
  confirmed strategy rules — do not present them as validated.
