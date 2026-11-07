"""
Service layer for the local research dashboard.

This is the ONLY module in the web layer that touches data loading, the
detector, ``BacktestEngine``, ``Reporter`` or ``ChartGenerator``. Replay and
instant backtests both drive ``BacktestEngine``; the browser only formats
events that the engine actually produced.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..backtesting.backtest_engine import BacktestConfig, BacktestEngine
from ..data.csv_data_provider import CSVDataProvider, DataValidationReport
from ..detection.abc_detector import ABCDetectorConfig, ReferenceABCDetector
from ..detection.swing_detector import SwingDetectorConfig
from ..domain.enums import SetupDirection
from ..exceptions import TradingBotError
from ..reporting.charts import ChartGenerator
from ..reporting.reporter import Reporter
from ..strategy.mathematical_strategy import MathematicalStrategy
from ..strategy.target_projection import build_target_projector
from .schemas import BacktestParams, DetectionParams

#: Upload cap for POST /api/validate (20 MB).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
#: Hard cap on candles per web run (local research; keeps memory bounded).
MAX_CANDLES = 20_000
#: Run-history cap; oldest runs are stopped and evicted.
MAX_RUNS = 50

_DATASET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.csv$")
_TIMEFRAME = re.compile(r"^(?P<symbol>.+)_(?P<tf>\d+[mhdw])$", re.IGNORECASE)


class RunNotFoundError(TradingBotError):
    """Raised when a run id is unknown (HTTP 404)."""


class RunNotFinishedError(TradingBotError):
    """Raised when artifacts are requested before a run has a result (HTTP 409)."""


def project_root() -> Path:
    """Repository root for an editable/source checkout."""
    return Path(__file__).resolve().parents[3]


def default_data_dir() -> Path:
    """Bundled dataset directory (env override: TRADINGBOT_DATA_DIR)."""
    configured = os.getenv("TRADINGBOT_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    candidate = project_root() / "data" / "sample"
    if candidate.is_dir():
        return candidate
    return (Path.cwd() / "data" / "sample").resolve()


def default_runs_dir() -> Path:
    """Directory for generated web artifacts (env: TRADINGBOT_RUNS_DIR)."""
    configured = os.getenv("TRADINGBOT_RUNS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return project_root() / "reports" / "web"


def resolve_dataset(data_dir: Path, name: str) -> Path:
    """Resolve a dataset name strictly inside ``data_dir`` (no traversal)."""
    if not _DATASET_NAME.match(name):
        raise TradingBotError(
            "Invalid dataset name. Use a bundled CSV name such as "
            "'sample_sinus_1h.csv'."
        )
    base = data_dir.resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_file():
        raise TradingBotError(f"Dataset not found: {name}")
    return path


def dataset_metadata(path: Path) -> Dict[str, Any]:
    """Infer display metadata from a dataset filename."""
    stem = path.stem
    match = _TIMEFRAME.match(stem)
    if match:
        return {"symbol": match.group("symbol"), "timeframe": match.group("tf")}
    return {"symbol": stem, "timeframe": None}


@dataclass
class DatasetBundle:
    name: str
    path: Path
    provider: CSVDataProvider
    report: DataValidationReport
    candles: List[Any]


@dataclass
class RunRecord:
    """One tracked backtest/replay run and its replay controls."""

    run_id: str
    mode: str
    dataset_name: str
    params: Dict[str, Any]
    candles: List[Any]
    validation: Dict[str, Any]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "idle"
    speed: float = 10.0
    events: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Any] = None
    live_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stopped: bool = False
    running: bool = False
    cursor: int = 0
    lock: threading.RLock = field(
        default_factory=threading.RLock, repr=False, compare=False
    )
    cond: threading.Condition = field(init=False, repr=False, compare=False)
    iterator: Optional[Iterator[Dict[str, Any]]] = field(
        default=None, repr=False, compare=False
    )
    thread: Optional[threading.Thread] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self.cond = threading.Condition(self.lock)


class RunRegistry:
    """In-memory run registry with deterministic (pollable) replay state."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        runs_dir: Optional[Path] = None,
        max_runs: int = MAX_RUNS,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.runs_dir = Path(runs_dir) if runs_dir else default_runs_dir()
        self.max_runs = max_runs
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.RLock()
        self._artifact_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------
    def list_datasets(self) -> List[Dict[str, Any]]:
        if not self.data_dir.is_dir():
            return []
        datasets: List[Dict[str, Any]] = []
        for path in sorted(self.data_dir.glob("*.csv")):
            if not _DATASET_NAME.match(path.name):
                continue
            item: Dict[str, Any] = {
                "name": path.name,
                **dataset_metadata(path),
                "candle_count": 0,
                "first_timestamp": None,
                "last_timestamp": None,
                "valid": False,
                "error": None,
            }
            try:
                provider = CSVDataProvider(str(path))
                report = provider.validate()
                candles = provider.get_candles()
                item.update(
                    {
                        "candle_count": report.candle_count,
                        "first_timestamp": candles[0].timestamp if candles else None,
                        "last_timestamp": candles[-1].timestamp if candles else None,
                        "valid": report.is_valid,
                    }
                )
            except TradingBotError as exc:
                item["error"] = str(exc)
            datasets.append(item)
        return datasets

    def load_dataset(self, name: str) -> DatasetBundle:
        path = resolve_dataset(self.data_dir, name)
        provider = CSVDataProvider(str(path))
        report = provider.validate()
        candles = provider.get_candles()
        if len(candles) > MAX_CANDLES:
            raise TradingBotError(
                f"Dataset has {len(candles)} candles; the web limit is {MAX_CANDLES}."
            )
        return DatasetBundle(name=name, path=path, provider=provider,
                             report=report, candles=candles)

    def validate_dataset(self, name: str) -> Dict[str, Any]:
        path = resolve_dataset(self.data_dir, name)
        provider = CSVDataProvider(str(path))
        report = provider.validate()
        return self._validation_payload(name, path, report, provider.get_candles())

    def validate_file(self, path: Path, display_name: str = "upload") -> Dict[str, Any]:
        """Validate an uploaded CSV. The client filename is never used on disk."""
        provider = CSVDataProvider(str(path))
        report = provider.validate()
        return self._validation_payload(
            display_name, path, report, provider.get_candles(), display_path=True
        )

    @staticmethod
    def _validation_payload(
        name: str,
        path: Path,
        report: DataValidationReport,
        candles: List[Any],
        display_path: bool = False,
    ) -> Dict[str, Any]:
        payload = report.to_dict()
        payload["path"] = name if display_path else str(path)
        payload["name"] = name
        payload["is_valid"] = report.is_valid
        payload.update(dataset_metadata(path))
        payload["first_timestamp"] = candles[0].timestamp if candles else None
        payload["last_timestamp"] = candles[-1].timestamp if candles else None
        return payload

    # ------------------------------------------------------------------
    # Detection (same detector/strategy as the CLI)
    # ------------------------------------------------------------------
    def detect(self, params: DetectionParams) -> Dict[str, Any]:
        bundle = self.load_dataset(params.dataset)
        swing = SwingDetectorConfig(
            left_window=params.left_window,
            right_window=params.right_window,
            min_separation=params.min_separation,
        )
        detector = ReferenceABCDetector(
            ABCDetectorConfig(
                swing_config=swing,
                min_distance=params.min_distance,
            )
        )
        strategy = MathematicalStrategy(detector=detector)
        wanted = (
            None if params.direction == "both"
            else SetupDirection(params.direction)
        )
        setups = []
        for candle in bundle.candles:
            for setup in strategy.feed(candle):
                if wanted is None or setup.direction == wanted:
                    setups.append(setup.to_dict())
        return {
            "dataset": bundle.name,
            "candle_count": len(bundle.candles),
            "setups_found": len(setups),
            "setups": setups,
            "assumptions": {
                "formula": "TARGET = (B + C) / A (confirmed)",
                "abc_detection": (
                    "CONFIGURABLE REFERENCE interpretation (not confirmed)"
                ),
            },
        }

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------
    def _build_engine(self, params: BacktestParams) -> BacktestEngine:
        swing = SwingDetectorConfig(
            left_window=params.left_window,
            right_window=params.right_window,
            min_separation=params.min_separation,
        )
        detector = ReferenceABCDetector(
            ABCDetectorConfig(
                swing_config=swing,
                min_distance=params.min_distance,
            )
        )
        strategy = MathematicalStrategy(
            detector=detector,
            projector=build_target_projector(params.target_projection),
        )
        config = BacktestConfig(
            target_mode=params.target_mode,
            invalidation_rule=params.invalidation_rule,
            max_candles_active=params.max_candles_active,
            allow_overlapping=params.allow_overlapping,
            allow_same_candle_activation=params.allow_same_candle_activation,
            fee=float(params.fee),
            slippage=float(params.slippage),
            spread=float(params.spread),
            target_projection=params.target_projection,
            max_active_setups=params.max_active_setups,
            direction=params.direction,
        )
        return BacktestEngine(strategy=strategy, config=config)

    def create_backtest(self, params: BacktestParams) -> RunRecord:
        bundle = self.load_dataset(params.dataset)
        engine = self._build_engine(params)
        result = engine.run(bundle.candles)  # same iter_run path
        record = RunRecord(
            run_id=self._new_id(),
            mode="backtest",
            dataset_name=bundle.name,
            params=params.engine_params(),
            candles=bundle.candles,
            validation=bundle.report.to_dict(),
            status="finished",
            result=result,
            live_metrics=result.metrics,
            cursor=len(bundle.candles),
        )
        self._add(record)
        return record

    def create_replay(self, params: BacktestParams, speed: float = 10.0) -> RunRecord:
        bundle = self.load_dataset(params.dataset)
        engine = self._build_engine(params)
        iterator = engine.iter_run(bundle.candles, include_live_metrics=True)
        record = RunRecord(
            run_id=self._new_id(),
            mode="replay",
            dataset_name=bundle.name,
            params=params.engine_params(),
            candles=bundle.candles,
            validation=bundle.report.to_dict(),
            status="paused",
            speed=max(1.0, min(200.0, float(speed))),
            iterator=iterator,
            cursor=0,
        )
        self._add(record)
        return record

    def _new_id(self) -> str:
        while True:
            candidate = uuid.uuid4().hex[:12]
            with self._lock:
                if candidate not in self._runs:
                    return candidate

    def _add(self, record: RunRecord) -> None:
        with self._lock:
            while len(self._runs) >= self.max_runs:
                self._evict_one_locked()
            self._runs[record.run_id] = record

    def _evict_one_locked(self) -> None:
        oldest_id = next(iter(self._runs))
        for run_id, candidate in self._runs.items():
            if candidate.status in {"finished", "failed", "idle"} and not candidate.running:
                oldest_id = run_id
                break
        victim = self._runs.pop(oldest_id)
        self._stop_record(victim)

    def require(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            raise RunNotFoundError(f"Unknown run: {run_id}")
        return record

    def has(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._runs

    # ------------------------------------------------------------------
    # Replay control
    # ------------------------------------------------------------------
    def control(
        self, run_id: str, action: str, speed: Optional[float] = None
    ) -> Dict[str, Any]:
        record = self.require(run_id)
        if action == "speed":
            if speed is None:
                raise TradingBotError("'speed' action requires a speed value")
            with record.lock:
                record.speed = max(1.0, min(200.0, float(speed)))
            return self.state(run_id, since=0)

        if action == "start":
            with record.cond:
                if record.status in {"finished", "failed", "stopped"}:
                    return self.state(run_id, since=0)
                record.running = True
                record.status = "replaying"
                if record.thread is None or not record.thread.is_alive():
                    record.thread = threading.Thread(
                        target=self._worker,
                        args=(record,),
                        name=f"replay-{record.run_id}",
                        daemon=True,
                    )
                    record.thread.start()
                record.cond.notify_all()
        elif action == "pause":
            with record.cond:
                if record.status == "replaying":
                    record.running = False
                    record.status = "paused"
                record.cond.notify_all()
        elif action == "step":
            with record.lock:
                if record.status in {"finished", "failed", "stopped"}:
                    return self.state(run_id, since=0)
                record.running = False
                record.status = "paused"
                self._advance(record)
                if record.status != "finished":
                    record.status = "paused" if not record.stopped else "finished"
                record.cond.notify_all()
        elif action == "stop":
            with record.cond:
                record.stopped = True
                record.running = False
                record.status = "finished"
                record.live_metrics = record.live_metrics
                iterator = record.iterator
                record.iterator = None
                record.cond.notify_all()
            if iterator is not None:
                try:
                    close = getattr(iterator, "close", None)
                    if close is not None:
                        close()
                except Exception:
                    pass
        else:
            raise TradingBotError(f"Unknown replay action: {action}")
        return self.state(run_id, since=0)

    def _worker(self, record: RunRecord) -> None:
        while True:
            with record.cond:
                while not record.running and not record.stopped:
                    record.cond.wait(timeout=0.5)
                if record.stopped:
                    return
                delay = 1.0 / max(1.0, record.speed)
            if not self._advance(record):
                return
            time.sleep(delay)

    def _advance(self, record: RunRecord) -> bool:
        """Pull exactly one event from the engine generator. Returns False when done."""
        with record.lock:
            if record.stopped or record.status in {"finished", "failed"}:
                return False
            if record.iterator is None:
                return False
            try:
                raw = next(record.iterator)
            except StopIteration:
                record.status = "finished"
                record.running = False
                record.cond.notify_all()
                return False
            except Exception as exc:  # engine failure: surface it, do not hide it
                record.error = str(exc)
                record.status = "failed"
                record.running = False
                record.events.append(
                    {
                        "type": "error",
                        "seq": len(record.events),
                        "message": str(exc),
                    }
                )
                record.cond.notify_all()
                return False

            if raw["type"] == "done":
                record.result = raw["result"]
                record.live_metrics = raw["metrics"]
                record.cursor = len(record.candles)
                record.status = "finished"
                record.running = False
                record.events.append(self._public_event(raw))
                record.cond.notify_all()
                return False

            record.cursor = int(raw["index"]) + 1
            if raw.get("metrics") is not None:
                record.live_metrics = raw["metrics"]
            record.events.append(raw)
            record.cond.notify_all()
            return True

    @staticmethod
    def _public_event(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Strip the non-serializable BacktestResult from the terminal event."""
        if raw.get("type") == "done":
            result = raw["result"]
            return {
                "type": "done",
                "seq": raw["seq"],
                "metrics": raw["metrics"],
                "progress": raw["progress"],
                "setup_count": len(result.setup_results),
                "warning_count": len(result.warnings),
                "duration_ms": result.duration_ms,
            }
        return raw

    def _stop_record(self, record: RunRecord) -> None:
        with record.cond:
            record.stopped = True
            record.running = False
            if record.status not in {"finished", "failed"}:
                record.status = "finished"
            iterator = record.iterator
            record.iterator = None
            record.cond.notify_all()
        if iterator is not None:
            try:
                close = getattr(iterator, "close", None)
                if close is not None:
                    close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # State / results / artifacts
    # ------------------------------------------------------------------
    def state(self, run_id: str, since: int = 0) -> Dict[str, Any]:
        record = self.require(run_id)
        since = max(0, int(since))
        with record.lock:
            events = [e for e in record.events if int(e["seq"]) >= since]
            next_seq = (
                max(int(e["seq"]) for e in record.events) + 1
                if record.events else 0
            )
            total = len(record.candles)
            progress = {
                "index": record.cursor,
                "total": total,
                "pct": round(record.cursor / total * 100.0, 2) if total else 100.0,
            }
            return {
                "run_id": record.run_id,
                "mode": record.mode,
                "status": record.status,
                "speed": record.speed,
                "dataset": record.dataset_name,
                "params": dict(record.params),
                "created_at": record.created_at,
                "progress": progress,
                "next": next_seq,
                "events": events,
                "error": record.error,
                "summary": self._summary_locked(record),
            }

    def _summary_locked(self, record: RunRecord) -> Dict[str, Any]:
        metrics = (
            record.result.metrics if record.result is not None
            else (record.live_metrics or {})
        )
        return {
            "run_id": record.run_id,
            "mode": record.mode,
            "status": record.status,
            "dataset": record.dataset_name,
            "params": dict(record.params),
            "created_at": record.created_at,
            "candle_count": len(record.candles),
            "progress": {
                "index": record.cursor,
                "total": len(record.candles),
            },
            "metrics": metrics,
        }

    def summary(self, run_id: str) -> Dict[str, Any]:
        record = self.require(run_id)
        with record.lock:
            return self._summary_locked(record)

    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._runs.values())
        summaries = {record.run_id: self.summary(record.run_id) for record in records}
        # Merge report-index entries persisted by earlier server processes.
        index_path = self.runs_dir / "run_index.json"
        if index_path.exists():
            try:
                entries = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                entries = []
            for entry in entries if isinstance(entries, list) else []:
                run_id = entry.get("run_id") or entry.get("base_name")
                if not run_id or run_id in summaries:
                    continue
                dataset = entry.get("dataset", {})
                summaries[run_id] = {
                    "run_id": run_id,
                    "mode": entry.get("mode", "report"),
                    "status": "finished",
                    "dataset": dataset.get("name") or dataset.get("path") or run_id,
                    "params": entry.get("config", {}),
                    "created_at": entry.get("generated_at"),
                    "candle_count": dataset.get("candle_count", 0),
                    "progress": {
                        "index": dataset.get("candle_count", 0),
                        "total": dataset.get("candle_count", 0),
                    },
                    "metrics": entry.get("metrics", {}),
                }
        return sorted(
            summaries.values(),
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )

    def full_result(self, run_id: str) -> Dict[str, Any]:
        record = self.require(run_id)
        with record.lock:
            if record.result is None:
                raise RunNotFinishedError(
                    f"Run {run_id} has not finished yet (status: {record.status})"
                )
            data = record.result.to_dict()
            data["run_id"] = record.run_id
            data["mode"] = record.mode
            data["status"] = record.status
            data["created_at"] = record.created_at
            data["dataset"]["name"] = record.dataset_name
            data["dataset"]["path"] = str(self.data_dir / record.dataset_name)
            data["dataset"]["validation"] = dict(record.validation)
            data["dataset"].update(dataset_metadata(Path(record.dataset_name)))
            data["candles"] = [c.to_dict() for c in record.candles]
            return data

    def ensure_artifacts(self, run_id: str) -> Path:
        record = self.require(run_id)
        with self._artifact_lock:
            out_dir = self.runs_dir / run_id
            json_path = out_dir / "report.json"
            chart_path = out_dir / "report.png"
            if json_path.exists() and chart_path.exists():
                return out_dir
            data = self.full_result(run_id)
            data.pop("candles", None)
            out_dir.mkdir(parents=True, exist_ok=True)
            Reporter(config={"reports_dir": str(out_dir)}).export_all(
                data, base_name="report"
            )
            with record.lock:
                candles = list(record.candles)
                result = record.result
            if result is None:  # pragma: no cover - full_result already checked
                raise RunNotFinishedError(f"Run {run_id} has no result")
            ChartGenerator(config={"charts_dir": str(out_dir)}).generate_backtest_chart(
                candles, result.setup_results, file_name="report",
                title=f"ABC Setups — {record.dataset_name}",
            )
            Reporter(config={"reports_dir": str(self.runs_dir)}).write_run_index(
                data, base_name=run_id, reports_dir=str(self.runs_dir)
            )
            return out_dir

    def report_text(self, run_id: str, fmt: str) -> Tuple[str, str]:
        out_dir = self.ensure_artifacts(run_id)
        mapping = {
            "json": ("report.json", "application/json"),
            "csv": ("report.csv", "text/csv"),
            "md": ("report.md", "text/markdown"),
        }
        if fmt not in mapping:
            raise TradingBotError(f"Unsupported report format: {fmt}")
        filename, media_type = mapping[fmt]
        return (out_dir / filename).read_text(encoding="utf-8"), media_type

    def chart_path(self, run_id: str) -> Path:
        return self.ensure_artifacts(run_id) / "report.png"

    def shutdown(self) -> None:
        with self._lock:
            records = list(self._runs.values())
            self._runs.clear()
        for record in records:
            self._stop_record(record)
