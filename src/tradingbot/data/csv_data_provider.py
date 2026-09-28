"""
CSV-based historical data provider.

STRICT VALIDATION POLICY:
Corrupted data is NEVER silently repaired. Any validation failure raises
DataProviderError with a precise message (row number and reason).
"""

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ..domain import Candle
from ..exceptions import DataProviderError
from .historical_data_provider import HistoricalDataProvider

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass
class DataValidationReport:
    """Result of validating a CSV dataset."""

    path: str
    row_count: int = 0
    candle_count: int = 0
    duplicates_removed: int = 0
    sorted: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "row_count": self.row_count,
            "candle_count": self.candle_count,
            "duplicates_removed": self.duplicates_removed,
            "sorted": self.sorted,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _parse_decimal(field_name: str, raw: Any, row_number: int) -> Decimal:
    if raw is None:
        raise DataProviderError(f"Row {row_number}: missing value for '{field_name}'")
    if isinstance(raw, float) and raw != raw:  # NaN check for floats
        raise DataProviderError(f"Row {row_number}: '{field_name}' is NaN")
    try:
        s = str(raw).strip()
    except Exception as e:
        raise DataProviderError(f"Row {row_number}: cannot read '{field_name}'") from e
    if s == "" or s.lower() in {"nan", "none", "null"}:
        raise DataProviderError(f"Row {row_number}: '{field_name}' is missing or NaN")
    try:
        d = Decimal(s)
    except InvalidOperation as e:
        raise DataProviderError(
            f"Row {row_number}: '{field_name}' is not a valid number: {raw!r}"
        ) from e
    if d.is_nan():
        raise DataProviderError(f"Row {row_number}: '{field_name}' is NaN")
    if d.is_infinite():
        raise DataProviderError(f"Row {row_number}: '{field_name}' is infinite")
    return d


class CSVDataProvider(HistoricalDataProvider):
    """CSV-based implementation of HistoricalDataProvider.

    Reads OHLCV data from CSV files with the required header:
        timestamp,open,high,low,close,volume

    * timestamps are Unix epoch MILLISECONDS (integers);
    * rows are sorted chronologically (ascending) after loading;
    * duplicate timestamps raise an error by default (configurable).

    Args:
        csv_file_path: Path to the CSV file containing historical data
        config: Optional dict; supported keys:
            allow_duplicates (bool, default False)
    """

    def __init__(self, csv_file_path: str, config: Optional[dict] = None):
        super().__init__(config)
        self.csv_file_path = csv_file_path
        self.allow_duplicates: bool = bool(self.config.get("allow_duplicates", False))

        if not os.path.exists(self.csv_file_path):
            raise DataProviderError(f"CSV file not found: {self.csv_file_path}")

        self._candles: Optional[List[Candle]] = None
        self._validation_report: Optional[DataValidationReport] = None

    # ------------------------------------------------------------------
    # Loading and validation
    # ------------------------------------------------------------------
    def _load(self) -> List[Candle]:
        if self._candles is not None:
            return self._candles

        import csv as _csv

        report = DataValidationReport(path=self.csv_file_path)

        try:
            with open(self.csv_file_path, newline="", encoding="utf-8-sig") as f:
                reader = _csv.DictReader(f)
                if reader.fieldnames is None:
                    raise DataProviderError(f"CSV file is empty: {self.csv_file_path}")
                header = [h.strip() for h in reader.fieldnames]
                missing = [c for c in REQUIRED_COLUMNS if c not in header]
                if missing:
                    raise DataProviderError(
                        f"CSV is missing required columns: {missing}. "
                        f"Required: {list(REQUIRED_COLUMNS)}"
                    )
                rows = list(reader)
        except DataProviderError:
            raise
        except OSError as e:
            raise DataProviderError(f"Failed to read CSV file: {e}") from e

        report.row_count = len(rows)
        if report.row_count == 0:
            raise DataProviderError(f"CSV file has no data rows: {self.csv_file_path}")

        def col_of(row: Dict[str, Any], name: str) -> Any:
            for k, v in row.items():
                if k is not None and k.strip() == name:
                    return v
            return None

        candles: List[Candle] = []
        seen_ts = set()
        for i, row in enumerate(rows, start=2):  # header is line 1
            ts_raw = col_of(row, "timestamp")
            if ts_raw is None or str(ts_raw).strip() == "":
                raise DataProviderError(f"Row {i}: missing timestamp")
            try:
                ts = int(str(ts_raw).strip())
            except ValueError as e:
                raise DataProviderError(
                    f"Row {i}: timestamp is not an integer: {ts_raw!r}"
                ) from e

            if ts in seen_ts:
                if self.allow_duplicates:
                    report.duplicates_removed += 1
                    report.warnings.append(
                        f"Row {i}: duplicate timestamp {ts} removed (allow_duplicates=True)"
                    )
                    continue
                raise DataProviderError(
                    f"Row {i}: duplicate timestamp {ts} (set allow_duplicates=True to drop)"
                )
            seen_ts.add(ts)

            try:
                o = _parse_decimal("open", col_of(row, "open"), i)
                h = _parse_decimal("high", col_of(row, "high"), i)
                low_v = _parse_decimal("low", col_of(row, "low"), i)
                c = _parse_decimal("close", col_of(row, "close"), i)
                v = _parse_decimal("volume", col_of(row, "volume"), i)
                candle = Candle(
                    timestamp=ts, open=o, high=h, low=low_v, close=c, volume=v
                )
            except DataProviderError:
                raise
            except Exception as e:
                raise DataProviderError(f"Row {i}: invalid OHLCV data: {e}") from e

            candles.append(candle)

        # Chronological ordering check (do not silently sort: report it).
        timestamps = [c.timestamp for c in candles]
        report.sorted = all(
            timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)
        )
        if not report.sorted:
            candles.sort(key=lambda c: c.timestamp)
            report.warnings.append(
                "Rows were not chronologically sorted; data has been sorted "
                "ascending by timestamp."
            )

        report.candle_count = len(candles)
        self._candles = candles
        self._validation_report = report
        return candles

    # ------------------------------------------------------------------
    # HistoricalDataProvider interface
    # ------------------------------------------------------------------
    def get_candles(
        self,
        symbol: str = "",
        start_time=None,
        end_time=None,
        timeframe: str = "1h",
    ) -> List[Candle]:
        """Retrieve validated candles from the CSV file.

        Optional time-range filtering (ms epoch) is applied after loading.
        """
        candles = self._load()
        if start_time is not None or end_time is not None:
            start_ms = _to_ms(start_time)
            end_ms = _to_ms(end_time)
            candles = [
                c for c in candles
                if (start_ms is None or c.timestamp >= start_ms)
                and (end_ms is None or c.timestamp <= end_ms)
            ]
        return list(candles)

    def is_available(self) -> bool:
        try:
            self._load()
            return True
        except DataProviderError:
            return False

    @property
    def validation_report(self) -> DataValidationReport:
        """Validation report from the last load (loads data if needed)."""
        self._load()
        assert self._validation_report is not None
        return self._validation_report

    def validate(self) -> DataValidationReport:
        """Explicitly load and validate the dataset."""
        self._load()
        return self.validation_report


def _to_ms(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    from datetime import datetime, timezone

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)
    return int(value)
