"""
Request schemas for the local research dashboard.

Every numeric input is bounded here (mirroring the CLI ranges) so the web layer
can never hand the engine values the CLI would reject.
"""

from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Bounds chosen to keep a local research run responsive and memory-safe.
MAX_WINDOW = 50
MAX_SEPARATION = 500
MAX_ACTIVE_CANDLES = 100_000
MAX_SETUPS = 100_000
MAX_RATE = 1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalculationRequest(_StrictModel):
    a: Decimal = Field(..., gt=0, max_digits=50)
    b: Decimal = Field(..., gt=0, max_digits=50)
    c: Decimal = Field(..., gt=0, max_digits=50)


class DetectionParams(_StrictModel):
    dataset: str = Field(..., min_length=1, max_length=255)
    left_window: int = Field(3, ge=1, le=MAX_WINDOW)
    right_window: int = Field(3, ge=1, le=MAX_WINDOW)
    min_separation: int = Field(1, ge=0, le=MAX_SEPARATION)
    min_distance: Decimal = Field(Decimal("0"), ge=0, max_digits=50)
    direction: Literal["both", "long", "short"] = "both"


class BacktestParams(DetectionParams):
    target_mode: Literal["high_low_reach", "close_reach"] = "high_low_reach"
    target_projection: Literal["c_anchored_ratio", "identity"] = "c_anchored_ratio"
    invalidation_rule: Literal["reference", "none"] = "reference"
    max_candles_active: int = Field(200, ge=1, le=MAX_ACTIVE_CANDLES)
    allow_overlapping: bool = True
    max_active_setups: int = Field(1000, ge=1, le=MAX_SETUPS)
    allow_same_candle_activation: bool = False
    fee: Decimal = Field(Decimal("0"), ge=0, le=MAX_RATE, max_digits=12)
    slippage: Decimal = Field(Decimal("0"), ge=0, le=MAX_RATE, max_digits=12)
    spread: Decimal = Field(Decimal("0"), ge=0, le=MAX_RATE, max_digits=12)

    def engine_params(self) -> dict:
        """Return a JSON-friendly copy (Decimals become strings)."""
        return self.model_dump(mode="json")


class ReplayParams(BacktestParams):
    # Values above 200 are clamped by the service (server-side speed cap).
    speed: float = Field(10.0, ge=1.0)


class ControlRequest(_StrictModel):
    action: Literal["start", "pause", "step", "stop", "speed"]
    speed: Optional[float] = Field(None, ge=1.0)


class ValidationRequest(_StrictModel):
    dataset: Optional[str] = Field(None, min_length=1, max_length=255)
