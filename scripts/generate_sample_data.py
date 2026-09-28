"""
Generate a deterministic sample OHLCV dataset.

The price path is a pure function of constants (no RNG): a slow sine wave with
a gentle trend, discretized into candles. Running this script twice produces
byte-identical output.

Usage:
    python scripts/generate_sample_data.py [output_path] [num_candles]
"""

import csv
import math
import sys
from typing import List

BASE_PRICE = 100.0
TREND_PER_CANDLE = 0.05          # gentle upward drift per candle
SINE_AMPLITUDE = 12.0            # swing amplitude
SINE_PERIOD = 40.0               # candles per full sine cycle
NOISE_PATTERNS = (               # deterministic pseudo-noise, cycles every 7 candles
    0.6, -0.4, 0.9, -0.7, 0.3, -0.9, 0.5,
)
START_MS = 1735689600000         # 2025-01-01T00:00:00Z
STEP_MS = 3_600_000              # 1 hour


def _candle(i: int) -> tuple:
    phase = 2.0 * math.pi * i / SINE_PERIOD
    mid = BASE_PRICE + TREND_PER_CANDLE * i + SINE_AMPLITUDE * math.sin(phase)
    noise = NOISE_PATTERNS[i % len(NOISE_PATTERNS)]
    open_price = mid + noise * 0.5
    close_price = mid - noise * 0.5
    high = max(open_price, close_price) + abs(noise) + 0.4
    low_price = min(open_price, close_price) - abs(noise) - 0.4
    volume = 1000.0 + 300.0 * math.sin(phase * 3.0) + 40.0 * (i % 5)
    ts = START_MS + i * STEP_MS
    return ts, round(open_price, 4), round(high, 4), round(low_price, 4), round(close_price, 4), round(volume, 2)


def generate(num_candles: int) -> List[tuple]:
    return [_candle(i) for i in range(num_candles)]


def write_csv(path: str, rows: List[tuple]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for ts, o, h, low_v, c, v in rows:
            writer.writerow([ts, o, h, low_v, c, v])


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/sample/sample_sinus_1h.csv"
    num_candles = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    rows = generate(num_candles)
    write_csv(out_path, rows)
    print(f"Wrote {len(rows)} candles to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
