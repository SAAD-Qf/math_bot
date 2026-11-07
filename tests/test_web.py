"""
Browser dashboard API tests (TestClient, deterministic polling — no sleeps).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tradingbot import __version__
from tradingbot.web import app as web_app
from tradingbot.web import create_app

DATASET = "sample_sinus_1h.csv"


def params(**overrides):
    payload = {
        "dataset": DATASET,
        "left_window": 3,
        "right_window": 3,
        "min_separation": 1,
        "min_distance": "0",
        "direction": "both",
        "target_mode": "high_low_reach",
        "target_projection": "c_anchored_ratio",
        "invalidation_rule": "reference",
        "max_candles_active": 200,
        "allow_overlapping": True,
        "max_active_setups": 1000,
        "allow_same_candle_activation": False,
        "fee": "0",
        "slippage": "0",
        "spread": "0",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(runs_dir=tmp_path / "runs")) as test_client:
        yield test_client


def _finish_replay(client, payload):
    created = client.post("/api/runs", json={**payload, "speed": 200})
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    response = None
    for _ in range(500):
        response = client.post(f"/api/runs/{run_id}/control", json={"action": "step"})
        assert response.status_code == 200, response.text
        if response.json()["status"] == "finished":
            break
    assert response is not None and response.json()["status"] == "finished"
    return run_id, response.json()


def test_health_and_version(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["mode"] == "research-only"
    assert body["extra_available"] is True


def test_index_page_renders_without_external_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "TARGET = (B + C) / A" in response.text
    assert "/static/style.css" in response.text
    assert "http://" not in response.text.replace("http://testserver", "")


def test_calculate_canonical_and_validation(client):
    response = client.post(
        "/api/calculate", json={"a": "100", "b": "150", "c": "125"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["target"] == "2.75"
    assert body["sum"] == "275"
    assert body["lines"][-1] == "TARGET = 2.75"

    for bad in ({"a": "0", "b": "150", "c": "125"},
                {"a": "-1", "b": "150", "c": "125"},
                {"a": "abc", "b": "150", "c": "125"}):
        assert client.post("/api/calculate", json=bad).status_code == 422


def test_datasets_listing(client):
    response = client.get("/api/datasets")
    assert response.status_code == 200
    datasets = {d["name"]: d for d in response.json()["datasets"]}
    assert DATASET in datasets
    item = datasets[DATASET]
    assert item["candle_count"] == 300
    assert item["valid"] is True
    assert item["first_timestamp"] < item["last_timestamp"]
    assert item["timeframe"] == "1h"


def test_validate_named_dataset_and_traversal_rejected(client):
    response = client.post("/api/validate", json={"dataset": DATASET})
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is True
    assert body["candle_count"] == 300

    for name in ("../pyproject.toml", "..\\pyproject.toml", "nope.csv", "/etc/passwd"):
        assert client.post("/api/validate", json={"dataset": name}).status_code == 422


def test_validate_upload_valid_invalid_and_oversized(client, monkeypatch):
    valid_bytes = Path("data/sample/sample.csv").read_bytes()
    response = client.post(
        "/api/validate",
        files={"file": ("../../client-name.csv", valid_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["candle_count"] == 5
    assert response.json()["name"] == "upload.csv"

    invalid = b"timestamp,open\n1,2\n"
    assert client.post(
        "/api/validate", files={"file": ("bad.csv", invalid, "text/csv")}
    ).status_code == 422

    monkeypatch.setattr(web_app, "MAX_UPLOAD_BYTES", 32)
    oversized = client.post(
        "/api/validate",
        files={"file": ("big.csv", b"x" * 128, "text/csv")},
    )
    assert oversized.status_code == 413


def test_detect_returns_real_setups(client):
    response = client.post("/api/detect", json={
        "dataset": DATASET,
        "left_window": 3,
        "right_window": 3,
        "min_separation": 1,
        "min_distance": "0",
        "direction": "both",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["setups_found"] > 0
    assert body["setups_found"] == len(body["setups"])
    setup = body["setups"][0]
    assert setup["a"]["candle_index"] < setup["b"]["candle_index"] < setup["c"]["candle_index"]
    assert setup["target"] is not None


def test_instant_backtest_result_and_artifacts(client):
    response = client.post("/api/backtest", json=params())
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    assert response.json()["summary"]["metrics"]["total_setups"] > 0

    full = client.get(f"/api/runs/{run_id}")
    assert full.status_code == 200
    data = full.json()
    assert data["mode"] == "backtest"
    assert data["status"] == "finished"
    assert len(data["candles"]) == 300
    assert data["dataset"]["name"] == DATASET
    assert "TARGET = (B + C) / A (confirmed)" in data["assumptions"]["formula"]
    assert data["metrics"]["total_setups"] == data["setup_count"]

    for fmt in ("json", "csv", "md"):
        artifact = client.get(f"/api/runs/{run_id}/report.{fmt}")
        assert artifact.status_code == 200
        assert len(artifact.text) > 0
    assert "## Assumptions" in client.get(f"/api/runs/{run_id}/report.md").text
    chart = client.get(f"/api/runs/{run_id}/chart.png")
    assert chart.status_code == 200
    assert chart.headers["content-type"] == "image/png"
    assert chart.content.startswith(b"\x89PNG")


def test_replay_polling_and_final_numbers_match_instant_backtest(client):
    instant = client.post("/api/backtest", json=params())
    assert instant.status_code == 200, instant.text
    instant_data = client.get(
        f"/api/runs/{instant.json()['run_id']}"
    ).json()

    run_id, state = _finish_replay(client, params())
    assert state["progress"] == {"index": 300, "total": 300, "pct": 100.0}
    assert state["events"][0]["seq"] == 0
    assert state["events"][-1]["type"] == "done"
    assert state["events"][-1]["setup_count"] == instant_data["setup_count"]

    replay_data = client.get(f"/api/runs/{run_id}").json()
    assert replay_data["mode"] == "replay"
    assert replay_data["metrics"] == instant_data["metrics"]
    assert replay_data["setup_count"] == instant_data["setup_count"]
    assert replay_data["assumptions"] == instant_data["assumptions"]


def test_replay_state_since_polling_is_incremental(client):
    created = client.post("/api/runs", json={**params(), "speed": 50})
    run_id = created.json()["run_id"]
    assert created.json()["state"]["status"] == "paused"

    first = client.post(
        f"/api/runs/{run_id}/control", json={"action": "step"}
    ).json()
    assert len(first["events"]) == 1
    assert first["next"] == 1

    second = client.get(f"/api/runs/{run_id}/state?since=1").json()
    assert second["events"] == [] or second["events"][0]["seq"] >= 1
    # Stepping again makes exactly one new event available from sequence 1.
    client.post(f"/api/runs/{run_id}/control", json={"action": "step"})
    third = client.get(f"/api/runs/{run_id}/state?since=1").json()
    assert [e["seq"] for e in third["events"]] == [1]


def test_pause_start_speed_and_stop_controls(client):
    created = client.post("/api/runs", json={**params(), "speed": 5})
    run_id = created.json()["run_id"]

    started = client.post(f"/api/runs/{run_id}/control", json={"action": "start"}).json()
    assert started["status"] in {"replaying", "paused", "finished"}
    paused = client.post(f"/api/runs/{run_id}/control", json={"action": "pause"}).json()
    assert paused["status"] in {"paused", "finished"}

    slowed = client.post(
        f"/api/runs/{run_id}/control", json={"action": "speed", "speed": 500}
    ).json()
    assert slowed["speed"] == 200.0

    stopped = client.post(f"/api/runs/{run_id}/control", json={"action": "stop"}).json()
    assert stopped["status"] == "finished"
    assert client.get(f"/api/runs/{run_id}").status_code == 409


def test_replay_stream_is_sse_and_ends(client):
    run_id, _ = _finish_replay(client, {**params(), "dataset": "sample.csv"})
    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: candle" in body
    assert "event: done" in body


def test_unknown_run_and_invalid_control(client):
    assert client.get("/api/runs/does-not-exist").status_code == 404
    assert client.get("/runs/does-not-exist").status_code == 404
    run_id = client.post("/api/runs", json=params()).json()["run_id"]
    response = client.post(
        f"/api/runs/{run_id}/control", json={"action": "teleport"}
    )
    assert response.status_code == 422


def test_run_history_contains_runs(client):
    first = client.post("/api/backtest", json=params()).json()["run_id"]
    second = client.post("/api/backtest", json=params()).json()["run_id"]
    history = client.get("/api/runs").json()["runs"]
    ids = {run["run_id"] for run in history}
    assert {first, second}.issubset(ids)
    entry = next(run for run in history if run["run_id"] == first)
    assert entry["dataset"] == DATASET
    assert "metrics" in entry


def test_report_json_is_valid_and_contains_setup_data(client):
    run_id = client.post("/api/backtest", json=params()).json()["run_id"]
    text = client.get(f"/api/runs/{run_id}/report.json").text
    data = json.loads(text)
    assert data["setup_count"] == len(data["setup_results"])
    assert "metrics" in data
