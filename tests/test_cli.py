"""
CLI tests: help, calculate, validate-data, detect, backtest, report.
"""

import json
import os

import pytest

from tradingbot.cli import main


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
