"""
FastAPI application for the local research dashboard.

The app is deliberately small: it validates requests, delegates all engine work
to :class:`RunRegistry`, and renders templates/JSON. No trading execution,
exchange connectivity, or external assets exist anywhere in this layer.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile

from .. import __version__
from ..exceptions import TradingBotError
from ..mathematical_engine import MathematicalEngine
from .schemas import (
    BacktestParams,
    CalculationRequest,
    ControlRequest,
    DetectionParams,
    ReplayParams,
    ValidationRequest,
)
from .service import (
    MAX_UPLOAD_BYTES,
    RunNotFinishedError,
    RunNotFoundError,
    RunRegistry,
)

_WEB_DIR = Path(__file__).resolve().parent


def _event_sse(event: Dict[str, Any]) -> str:
    return (
        f"event: {event['type']}\n"
        f"data: {json.dumps(event, default=str, separators=(',', ':'))}\n\n"
    )


def create_app(
    data_dir: Optional[Path] = None, runs_dir: Optional[Path] = None
) -> FastAPI:
    """Create the dashboard app (also used by tests with temporary data dirs)."""
    registry = RunRegistry(data_dir=data_dir, runs_dir=runs_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            registry.shutdown()

    app = FastAPI(
        title="Mathematical Trading Bot — Research Dashboard",
        version=__version__,
        description=(
            "Research/backtesting only. No live trading, order execution or "
            "exchange connectivity."
        ),
        lifespan=lifespan,
    )
    app.state.registry = registry
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
    templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------
    @app.exception_handler(RunNotFoundError)
    async def _not_found(_: Request, exc: RunNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"error": str(exc), "type": "not_found"}
        )

    @app.exception_handler(RunNotFinishedError)
    async def _not_finished(_: Request, exc: RunNotFinishedError) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"error": str(exc), "type": "not_finished"}
        )

    @app.exception_handler(TradingBotError)
    async def _invalid(_: Request, exc: TradingBotError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "type": type(exc).__name__},
        )

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": str(exc), "type": "ValueError"}
        )

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "datasets": registry.list_datasets(),
                "formula": "TARGET = (B + C) / A",
                "version": __version__,
            },
        )

    @app.get("/runs/{run_id}")
    async def results_page(request: Request, run_id: str):
        if not registry.has(run_id):
            raise HTTPException(status_code=404, detail="Unknown run")
        return templates.TemplateResponse(
            request,
            "results.html",
            {
                "run_id": run_id,
                "formula": "TARGET = (B + C) / A",
                "version": __version__,
            },
        )

    # ------------------------------------------------------------------
    # JSON API
    # ------------------------------------------------------------------
    @app.get("/api/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "web": True,
            "extra_available": True,
            "mode": "research-only",
        }

    @app.get("/api/datasets")
    async def datasets() -> Dict[str, Any]:
        return {"datasets": registry.list_datasets()}

    @app.post("/api/calculate")
    async def calculate(payload: CalculationRequest) -> Dict[str, Any]:
        result = MathematicalEngine().calculate_target(payload.a, payload.b, payload.c)
        data = result.to_dict()
        data["lines"] = [
            f"A      = {result.a}",
            f"B      = {result.b}",
            f"C      = {result.c}",
            f"B + C  = {result.sum}",
            f"TARGET = {result.target}",
        ]
        return data

    @app.post("/api/validate")
    async def validate(request: Request) -> Dict[str, Any]:
        content_type = request.headers.get("content-type", "").lower()
        if content_type.startswith("application/json"):
            payload = ValidationRequest.model_validate(await request.json())
            if not payload.dataset:
                raise TradingBotError("Provide a dataset name or upload a CSV file")
            return registry.validate_dataset(payload.dataset)

        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            dataset = form.get("dataset")
            if isinstance(upload, UploadFile):
                return await _validate_upload(upload)
            if isinstance(dataset, str) and dataset:
                return registry.validate_dataset(dataset)
            raise TradingBotError("Provide a dataset name or upload a CSV file")

        raise HTTPException(
            status_code=415,
            detail="Use application/json or multipart/form-data",
        )

    async def _validate_upload(upload: UploadFile) -> Dict[str, Any]:
        # The client filename is intentionally discarded: never used on disk.
        handle, temp_name = tempfile.mkstemp(prefix="tradingbot-upload-", suffix=".csv")
        size = 0
        try:
            with open(handle, "wb") as target:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} "
                                "MB limit"
                            ),
                        )
                    target.write(chunk)
            return registry.validate_file(Path(temp_name), display_name="upload.csv")
        finally:
            try:
                await upload.close()
            except Exception:
                pass
            Path(temp_name).unlink(missing_ok=True)

    @app.post("/api/detect")
    async def detect(payload: DetectionParams) -> Dict[str, Any]:
        return registry.detect(payload)

    @app.post("/api/backtest")
    async def backtest(payload: BacktestParams) -> Dict[str, Any]:
        record = registry.create_backtest(payload)
        return {"run_id": record.run_id, "summary": registry.summary(record.run_id)}

    @app.get("/api/runs")
    async def list_runs() -> Dict[str, Any]:
        return {"runs": registry.history()}

    @app.post("/api/runs")
    async def create_replay(payload: ReplayParams) -> Dict[str, Any]:
        record = registry.create_replay(payload, speed=payload.speed)
        return {
            "run_id": record.run_id,
            "state": registry.state(record.run_id, since=0),
        }

    @app.post("/api/runs/{run_id}/control")
    async def control(run_id: str, payload: ControlRequest) -> Dict[str, Any]:
        return registry.control(run_id, payload.action, payload.speed)

    @app.get("/api/runs/{run_id}/state")
    async def state(
        run_id: str, since: int = Query(0, ge=0)
    ) -> Dict[str, Any]:
        return registry.state(run_id, since=since)

    @app.get("/api/runs/{run_id}/stream")
    async def stream(request: Request, run_id: str) -> StreamingResponse:
        registry.require(run_id)  # 404 before the response starts

        async def event_source() -> AsyncIterator[str]:
            seq = 0
            last_heartbeat = time.monotonic()
            while True:
                if await request.is_disconnected():
                    return
                current = registry.state(run_id, since=seq)
                for event in current["events"]:
                    yield _event_sse(event)
                    seq = int(event["seq"]) + 1
                if current["status"] in {"finished", "failed"}:
                    return
                if time.monotonic() - last_heartbeat >= 15.0:
                    yield ": heartbeat\n\n"
                    last_heartbeat = time.monotonic()
                await asyncio.sleep(0.1)

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/runs/{run_id}")
    async def full_result(run_id: str) -> Dict[str, Any]:
        return registry.full_result(run_id)

    @app.get("/api/runs/{run_id}/chart.png")
    async def chart(run_id: str) -> FileResponse:
        return FileResponse(
            registry.chart_path(run_id), media_type="image/png",
            filename=f"{run_id}-chart.png",
        )

    @app.get("/api/runs/{run_id}/report.json")
    async def report_json(run_id: str) -> Response:
        text, media_type = registry.report_text(run_id, "json")
        return Response(text, media_type=media_type)

    @app.get("/api/runs/{run_id}/report.csv")
    async def report_csv(run_id: str) -> Response:
        text, media_type = registry.report_text(run_id, "csv")
        return Response(text, media_type=media_type)

    @app.get("/api/runs/{run_id}/report.md")
    async def report_markdown(run_id: str) -> Response:
        text, media_type = registry.report_text(run_id, "md")
        return Response(text, media_type=media_type)

    return app
