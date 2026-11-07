"""
CLI tests: help, calculate, validate-data, detect, backtest, report.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tradingbot.cli import main
from tradingbot.exceptions import TradingBotError
from tradingbot.reporting import charts as chart_module


def test_module_entrypoint_version():
    completed = subprocess.run(
        [sys.executable, "-m", "tradingbot", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "tradingbot" in completed.stdout


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("calculate", "validate-data", "detect", "backtest", "report"):
        assert cmd in out


def test_calculate_canonical(capsys):
    rc = main(["calculate", "--a", "100", "--b", "150", "--c", "125"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A      = 100" in out
    assert "B      = 150" in out
    assert "C      = 125" in out
    assert "B + C  = 275" in out
    assert "TARGET = 2.75" in out


def test_calculate_json(capsys):
    rc = main(["calculate", "--a", "100", "--b", "150", "--c", "125", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["target"] == "2.75"
    assert parsed["sum"] == "275"


def test_calculate_rejects_zero(capsys):
    rc = main(["calculate", "--a", "0", "--b", "150", "--c", "125"])
    assert rc == 1
    assert "Error" in capsys.readouterr().err


def test_calculate_rejects_garbage(capsys):
    rc = main(["calculate", "--a", "abc", "--b", "150", "--c", "125"])
    assert rc == 1


def test_validate_data_ok(sample_csv, capsys):
    rc = main(["validate-data", "--file", sample_csv])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PASSED" in out
    assert "Candles:            3" in out


def test_validate_data_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("timestamp,open\n1,2\n", encoding="utf-8")
    rc = main(["validate-data", "--file", str(bad)])
    assert rc == 1
    assert "INVALID" in capsys.readouterr().err


def test_detect(sample_csv, capsys):
    rc = main(["detect", "--file", sample_csv])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Setups found" in out
    assert "reference detector" in out


def test_detect_sine_dataset(big_sample_csv, capsys):
    rc = main(["detect", "--file", big_sample_csv])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Setups found:" in out
    assert "TARGET =" in out


def test_backtest(big_sample_csv, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["backtest", "--file", big_sample_csv, "--no-charts"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Backtest completed" in out
    assert "Total setups:" in out


def test_backtest_json(big_sample_csv, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["backtest", "--file", big_sample_csv, "--no-charts", "--json"])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert "metrics" in parsed
    assert "assumptions" in parsed


def test_report_generates_outputs(big_sample_csv, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main([
        "report", "--file", big_sample_csv,
        "--reports-dir", "reports", "--charts-dir", "charts",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "JSON:" in out and "CSV:" in out and "Markdown:" in out
    assert os.path.exists("reports/backtest.json")
    assert os.path.exists("reports/backtest.csv")
    assert os.path.exists("reports/backtest.md")
    assert os.path.exists("charts/backtest.png")


def test_backtest_chart_generated(big_sample_csv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["backtest", "--file", big_sample_csv])
    assert rc == 0
    assert os.path.exists("charts/backtest.png")


def test_backtest_exposes_cost_and_engine_flags(big_sample_csv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main([
        "backtest", "--file", big_sample_csv,
        "--fee", "0.001", "--slippage", "0.0005", "--spread", "0.0002",
        "--no-allow-overlapping", "--max-active-setups", "5",
        "--allow-same-candle-activation", "--direction", "long",
        "--charts-dir", "custom-charts",
    ])
    assert rc == 0
    assert os.path.exists(os.path.join("custom-charts", "backtest.png"))


def test_allow_duplicates_flag_on_backtest(sample_csv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lines = Path(sample_csv).read_text(encoding="utf-8").splitlines()
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        "\n".join([lines[0], lines[1], lines[1], lines[2], lines[3]]) + "\n",
        encoding="utf-8",
    )

    assert main(["backtest", "--file", str(duplicate), "--no-charts"]) == 1
    assert main([
        "backtest", "--file", str(duplicate), "--allow-duplicates", "--no-charts"
    ]) == 0


def test_report_chart_failure_is_clean_and_writes_index(
    big_sample_csv, tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)

    def boom(*args, **kwargs):
        raise TradingBotError("chart unavailable")

    monkeypatch.setattr(chart_module.ChartGenerator, "generate_backtest_chart", boom)
    rc = main([
        "report", "--file", big_sample_csv,
        "--reports-dir", "reports", "--charts-dir", "charts",
    ])
    assert rc == 0
    assert "Chart error: chart unavailable" in capsys.readouterr().err
    assert os.path.exists("reports/backtest.json")

    index = json.loads(Path("reports/run_index.json").read_text(encoding="utf-8"))
    assert len(index) == 1
    assert index[0]["base_name"] == "backtest"
    assert "total_setups" in index[0]["metrics"]
