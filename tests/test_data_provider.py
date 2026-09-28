"""
Tests for the CSV data provider and strict validation.
"""

import os
from decimal import Decimal

import pytest

from tradingbot.data.csv_data_provider import CSVDataProvider
from tradingbot.exceptions import DataProviderError

HEADER = "timestamp,open,high,low,close,volume\n"


def _write(tmp_path, name, rows, header=HEADER):
    path = tmp_path / name
    path.write_text(header + "".join(rows), encoding="utf-8")
    return str(path)


def test_loads_phase0_sample():
    csv_path = "data/sample/sample.csv"
    assert os.path.exists(csv_path)
    provider = CSVDataProvider(csv_file_path=csv_path)
    assert provider.is_available() is True
    candles = provider.get_candles(symbol="BTCUSDT")
    assert len(candles) == 5
    assert candles[0].timestamp == 1609459200000
    assert candles[0].open == Decimal("100.0")
    assert candles[0].high == Decimal("105.0")
    assert candles[0].low == Decimal("95.0")
    assert candles[0].close == Decimal("102.0")
    assert candles[0].volume == Decimal("1000.0")


def test_nonexistent_file_raises():
    with pytest.raises(DataProviderError, match="not found"):
        CSVDataProvider(csv_file_path="nonexistent_file.csv")


def test_valid_file(tmp_path, sample_csv):
    provider = CSVDataProvider(sample_csv)
    candles = provider.get_candles()
    assert len(candles) == 3
    report = provider.validate()
    assert report.is_valid
    assert report.sorted


def test_missing_column(tmp_path):
    path = _write(tmp_path, "missing.csv", [
        "1609459200000,100,105,95,102\n",  # no volume column
    ], header="timestamp,open,high,low,close\n")
    with pytest.raises(DataProviderError, match="missing required columns"):
        CSVDataProvider(path).get_candles()


def test_malformed_number(tmp_path):
    path = _write(tmp_path, "badnum.csv", [
        "1609459200000,abc,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="not a valid number"):
        CSVDataProvider(path).get_candles()


def test_nan_value(tmp_path):
    path = _write(tmp_path, "nan.csv", [
        "1609459200000,nan,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="NaN"):
        CSVDataProvider(path).get_candles()


def test_infinity_value(tmp_path):
    path = _write(tmp_path, "inf.csv", [
        "1609459200000,inf,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="infinite"):
        CSVDataProvider(path).get_candles()


def test_missing_value(tmp_path):
    path = _write(tmp_path, "empty.csv", [
        "1609459200000,,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="missing"):
        CSVDataProvider(path).get_candles()


def test_non_integer_timestamp(tmp_path):
    path = _write(tmp_path, "ts.csv", [
        "2021-01-01,100,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="timestamp is not an integer"):
        CSVDataProvider(path).get_candles()


def test_duplicate_timestamps_rejected_by_default(tmp_path):
    path = _write(tmp_path, "dup.csv", [
        "1609459200000,100,105,95,102,10\n",
        "1609459200000,100,105,95,102,10\n",
    ])
    with pytest.raises(DataProviderError, match="duplicate timestamp"):
        CSVDataProvider(path).get_candles()


def test_duplicate_timestamps_droppable(tmp_path):
    path = _write(tmp_path, "dup2.csv", [
        "1609459200000,100,105,95,102,10\n",
        "1609459200000,100,105,95,102,10\n",
        "1609462800000,100,105,95,102,10\n",
    ])
    provider = CSVDataProvider(path, config={"allow_duplicates": True})
    candles = provider.get_candles()
    assert len(candles) == 2
    report = provider.validate()
    assert report.duplicates_removed == 1
    assert any("duplicate" in w for w in report.warnings)


def test_unsorted_rows_sorted_with_warning(tmp_path):
    path = _write(tmp_path, "unsorted.csv", [
        "1609462800000,100,105,95,102,10\n",
        "1609459200000,100,105,95,102,10\n",
    ])
    provider = CSVDataProvider(path)
    candles = provider.get_candles()
    assert candles[0].timestamp < candles[1].timestamp
    report = provider.validate()
    assert any("sorted" in w for w in report.warnings)


def test_invalid_ohlc_relationship(tmp_path):
    path = _write(tmp_path, "bad_ohlc.csv", [
        "1609459200000,100,90,95,102,10\n",  # high < open
    ])
    with pytest.raises(DataProviderError, match="Invalid|inconsistent|high"):
        CSVDataProvider(path).get_candles()


def test_time_range_filter(tmp_path, sample_csv):
    provider = CSVDataProvider(sample_csv)
    candles = provider.get_candles(start_time=1609462800000)
    assert len(candles) == 2
    candles = provider.get_candles(start_time=1609459200000, end_time=1609462800000)
    assert len(candles) == 2


def test_validation_report_dict(tmp_path, sample_csv):
    provider = CSVDataProvider(sample_csv)
    d = provider.validate().to_dict()
    assert d["candle_count"] == 3
    assert d["row_count"] == 3
    assert d["sorted"] is True
