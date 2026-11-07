# TODO — Remaining Work

Baseline verified **2026-11-07** (see `.freebuff/memory/session-2026-11-07.md`):

* 151 tests pass; `ruff check` clean; `mypy src` clean.
* Coverage: **84.8%** overall.
* Environment: `.venv/` (Python 3.15.2), installed with `pip install -e ".[dev]"`.

Guiding rule: this project is **research/backtesting only** — no live trading, no
order execution, no exchange connectivity, no API keys. Keep that true.

---

## Decisions locked for the UI

1. **Stack:** FastAPI + uvicorn + Jinja2 + vanilla JS. No React/Vue, no build
   step, no CDN — the dashboard must work offline and with one `pip install`.
2. **"Signals monitored" means replay monitoring, not a live market feed.**
   The project has no data feed by design. The dashboard streams bundled
   historical candles through the real engine at a controllable speed and shows
   every signal as it fires — same code path, same no-look-ahead guarantees.
   A live feed would be a separate decision (data provider, credentials, terms)
   and is **out of scope** until you choose it.
3. **One engine path.** Replay and instant backtest must both drive
   `BacktestEngine`; no duplicated evaluation logic in the web layer.
4. **Server renders truth, client renders pictures.** Metrics, statuses and
   transitions come from `SetupResult.to_dict()` / `compute_metrics()`.
   The browser only formats and draws.

### The signal vocabulary the UI must show (already in the domain)

| Concept | Values (source of truth) |
|---|---|
| Setup lifecycle `SetupStatus` | `pending`, `active`, `target_reached`, `invalidated`, `expired` |
| Target evaluation `TargetStatus` | `not_evaluated`, `pending`, `reached`, `not_reached` |
| Invalidation `InvalidationStatus` | `not_evaluated`, `none`, `invalidated`, `expired` |
| Direction `SetupDirection` | `long`, `short` |
| Point roles `PointRole` | `A`, `B`, `C`, `swing_high`, `swing_low` |
| Per-setup record `SetupResult` | A/B/C price points, `target`, `activated_at`, `reached_at`, `invalidated_at`, `expiry_at`, `candles_monitored`, MFE, MAE, `gross_outcome`, `cost_impact`, `state_transitions` |
| Metrics `compute_metrics()` | totals, hit/invalidation/completion rates, `still_active_at_end`, duration avg/median/min/max, `long`/`short` breakdown, `setup_frequency_per_100_candles`, MFE/MAE averages |
| Engine warnings | duplicate setup suppressed, overlap policy skip, `max_active_setups` reached |
| Assumptions block | formula (confirmed) vs detection/evaluation/invalidation (interpretations) |

---

## Phase 1 — Browser UI (**the main missing capability**, do first)

### 1a. Dependencies and package layout

- [ ] 1. `pyproject.toml`: add `web = ["fastapi", "uvicorn[standard]", "jinja2",
      "python-multipart"]`; add `httpx` to `dev` (Starlette `TestClient`).
      Install into `.venv`; keep `pip install -e ".[dev]"` working without it.
- [ ] 2. Create:
      - `src/tradingbot/web/__init__.py` — exports `create_app`
      - `src/tradingbot/web/app.py` — app factory, template/static mounts,
        JSON error handlers (`TradingBotError` → 422, unknown → 404)
      - `src/tradingbot/web/schemas.py` — Pydantic request/response models,
        with bounds on every numeric parameter (mirror CLI ranges)
      - `src/tradingbot/web/service.py` — `RunRegistry` + engine drivers; the
        only place that touches `CSVDataProvider`, `BacktestEngine`, `Reporter`,
        `ChartGenerator`
      - `src/tradingbot/web/templates/{base,index,results}.html`
      - `src/tradingbot/web/static/{style.css,app.js,chart.js}`

### 1b. Engine change for replay (small, test-covered)

- [ ] 3. Add `BacktestEngine.iter_run(candles)` — a generator yielding one event
      per candle: the candle, newly detected setups, activated/invalidated/
      completed updates, and warnings. Re-implement `run()` as
      `iter_run()` + aggregation so there is exactly **one** evaluation path.
- [ ] 4. Prove equivalence: new test asserts `run()` results are identical
      (setups, statuses, timestamps, metrics, warnings) to consuming
      `iter_run()`. All 151 existing tests must stay green — they are the
      no-look-ahead contract.

### 1c. Endpoints

Pages:
- [ ] 5. `GET /` — control panel + dataset picker + parameter form.
- [ ] 6. `GET /runs/{run_id}` — results/replay page.

JSON API:
- [ ] 7. `GET /api/health` → status, version, extra-availability.
- [ ] 8. `GET /api/datasets` → bundled CSVs in `data/sample`: name, candle
      count, first/last timestamp, symbol/timeframe.
- [ ] 9. `POST /api/calculate` → `{a,b,c}` → target + the exact formula lines.
- [ ] 10. `POST /api/validate` → dataset name **or** upload → validation report
      (rows, candles, sorted, duplicates, warnings).
- [ ] 11. `POST /api/detect` → dataset + swing/min-distance/direction → setups.
- [ ] 12. `POST /api/backtest` → dataset + full config → `{run_id, summary}`;
      runs instantly, stores artifacts.
- [ ] 13. `POST /api/runs` → create a replay run `{run_id}` and start it
      **paused**; `POST /api/runs/{id}/control` → `start|pause|step|stop|speed`.
- [ ] 14. `GET /api/runs/{id}/stream` → **SSE** (one-way, no WebSocket needed):
      `candle`, `setup_detected`, `setup_state_changed`, `warning`, `metrics`,
      `done`. Heartbeat comment every 15 s; close on client disconnect.
- [ ] 15. `GET /api/runs/{id}/state?since={n}` → polling fallback with the same
      event shape (also what tests use — no timing flakiness).
- [ ] 16. `GET /api/runs/{id}` → full result JSON.
- [ ] 17. `GET /api/runs/{id}/chart.png` → matplotlib PNG (archived artifact).
- [ ] 18. `GET /api/runs/{id}/report.json|.csv|.md` → via existing `Reporter`.

### 1d. The dashboard itself

Layout, top to bottom (single page, dark theme, responsive ≥1024 px, usable on
mobile, keyboard operable, no external assets):

- [ ] 19. **Header:** project name, confirmed formula `TARGET = (B + C) / A`,
      dataset + parameters summary, run state (`idle | replaying | paused |
      finished | failed`), current candle timestamp / index / progress.
- [ ] 20. **KPI strip** (live-updating): total setups, currently active, target
      hit rate, invalidation rate, completion rate, avg duration, setups per
      100 candles.
- [ ] 21. **Signals table** (the core): one row per setup — direction, A/B/C
      values with timestamps, target, current status, candles monitored, MFE,
      MAE, cost impact. Sortable/filterable by direction and status. Status
      shown as **text label + color**, never color alone. New/updated rows
      highlighted briefly.
- [ ] 22. **Signal detail drawer:** clicking a row shows the state-transition
      timeline from `state_transitions` (timestamp, previous → new, reason,
      candle index) plus the arithmetic for that target.
- [ ] 23. **Price chart panel:** client-side `<canvas>` candlesticks from
      streamed candles, with swing markers, A/B/C labels, dashed target level
      per active setup, and outcome markers (reached ★ / invalidated ✕ /
      expired ◼). Server-side PNG stays the downloadable artifact — do not
      regenerate matplotlib per candle.
- [ ] 24. **Direction breakdown panel:** the `long`/`short` metric blocks side
      by side.
- [ ] 25. **Warnings feed:** engine warnings (duplicate suppressed, overlap
      skipped, max-active reached) with candle index, newest first.
- [ ] 26. **Assumptions panel:** renders `result.assumptions` verbatim, making
      clear the formula is confirmed while detection/projection/invalidation are
      interpretations. This is a required part of an honest UI.
- [ ] 27. **Run history:** last N runs (dataset, params, hit rate, timestamp)
      with a comparison table for two selected runs.
- [ ] 28. **Replay controls:** start/pause/step/stop, speed slider
      (1×–200× candles/s, clamped server-side), and reset.

### 1e. CLI + safety

- [ ] 29. `python -m tradingbot serve --host 127.0.0.1 --port 8000` (and
      `tradingbot serve`); friendly error if the `web` extra is missing.
      No auto-reload/`debug=True` in normal operation.
- [ ] 30. Limits: max upload size (e.g. 20 MB), max candles per run, dataset
      names resolved **inside** `data/` only (no path traversal), client
      filenames never used on disk, one active replay per run id, evict old runs
      (cap ~50) and stop orphaned threads.

### 1f. Verification

- [ ] 31. `tests/test_web.py` with `TestClient`: health; calculate incl.
      100/150/125; dataset list; validate; backtest on `sample_sinus_1h.csv`;
      replay state-polling end-to-end (deterministic, no sleeps); unknown run →
      404; oversized/invalid upload → 4xx; report/chart artifact endpoints.
- [ ] 32. `tests/test_backtest_stream.py`: `iter_run` ⇄ `run` equivalence and
      no-look-ahead invariance (setup never activates on its own C candle).
- [ ] 33. Manual: start server in the background, poll `/api/health`, open
      `http://127.0.0.1:8000` in Chrome, run a replay at moderate speed, confirm
      signals appear and end states match the instant backtest for the same
      dataset/params.

**Done when:** the dashboard opens in a browser, replays
`data/sample/sample_sinus_1h.csv` while showing every signal state live, its
final numbers match the CLI `report` output for identical parameters, and the
new tests pass with ruff/mypy clean.

---

## Phase 2 — CLI / config gaps (small, high value)

- [ ] 34. **Duplicate, partly dead config.** `tradingbot.config.BacktestConfig`
      and `backtesting.backtest_engine.BacktestConfig` are different classes;
      `Config`/`StrategyConfig`/`DataProviderConfig` never reach the CLI or
      engine (only `LoggingConfig` is used). Pick one source of truth — the web
      UI's parameter schema should build it — and delete the duplicate.
- [ ] 35. **Cost model unreachable.** `fee`, `slippage`, `spread`,
      `allow_overlapping`, `max_active_setups`, `allow_same_candle_activation`
      are implemented but have **no CLI flags**.
- [ ] 36. `cmd_backtest` hardcodes `charts_dir="charts"`; add the directory
      options it ignores.
- [ ] 37. `cmd_report` calls `ChartGenerator` without `try/except` — chart
      failure gives a traceback while `cmd_backtest` fails cleanly.
- [ ] 38. `--allow-duplicates` exists only on `validate-data`; add it to
      `detect`, `backtest`, `report`.
- [ ] 39. Dead dependencies: `pandas` and `numpy` have zero references in the
      whole repo. Drop them (recommended) or put them to actual use.
- [ ] 40. Unused config fields: `initial_capital`, `max_drawdown`,
      `max_position_size`, `enable_logging` feed nothing — implement a
      position/P&L model or remove them and the docs that mention them.

---

## Phase 3 — Strategy completeness (blocked on specification)

- [ ] 41. Only `TARGET = (B + C) / A` is confirmed. Detection
      (`ReferenceABCDetector`), price projection (`c_anchored_ratio`) and
      invalidation are documented interpretations. Get the real rules before
      calling any UI number "the strategy".
- [ ] 42. Once the rules exist, add alternative detector/projector
      implementations and let the UI compare them side by side (the interfaces
      already exist).

---

## Phase 4 — Quality / operations

- [ ] 43. Coverage thin spots: `config.py` 66.7%, `logging.py` 48.2%,
      `strategy/strategy.py` 42.9% (legacy ABC), `mathematical_strategy.py`
      62.5%, `historical_data_provider.py` 54.2%, `__main__.py` 0%.
- [ ] 44. CI (`.github/workflows/` is absent): ruff + mypy + pytest on Python
      3.10–3.13, Windows + Ubuntu.
- [ ] 45. `pyproject.toml` license metadata is deprecated (setuptools drops it
      after **2027-02-18**); switch to SPDX `license = "MIT"`.
- [ ] 46. Classifiers claim support only through 3.13, while everything is
      verified on 3.15.2 — update them.
- [ ] 47. Reports overwrite each run; add a run index so history is comparable
      (the UI run history can read it).
- [ ] 48. Only one 300-candle sample dataset; add larger and adversarial
      fixtures, plus walk-forward evaluation.
- [ ] 49. Optional: `Dockerfile` for reproducible research runs.

---

## Explicit non-goals (do **not** build without an explicit decision)

Live trading, order execution, fills, leverage, exchange APIs, API keys, broker
accounts. Also no live market-data feed, no P&L/equity-curve simulation, and no
deployment/hosting until you choose them.
