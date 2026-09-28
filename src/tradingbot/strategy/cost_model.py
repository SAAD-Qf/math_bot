"""
Optional cost model for financial execution simulation.

IMPORTANT SEPARATION:
Mathematical target success and profitability are DIFFERENT concepts. The cost
model only produces an *informational* cost estimate; it never influences
whether a mathematical target is reached. Default costs are zero.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

ZERO = Decimal('0')


class CostModel(ABC):
    """Interface for cost models."""

    @abstractmethod
    def estimate_cost(self, notional: Decimal) -> Decimal:
        """Estimate the absolute cost of executing ``notional`` worth of value."""
        raise NotImplementedError

    def describe(self) -> dict:
        return {"cost_model_class": type(self).__name__}


class ZeroCostModel(CostModel):
    """Default: no fees, no slippage, no spread."""

    def estimate_cost(self, notional: Decimal) -> Decimal:
        return ZERO

    def describe(self) -> dict:
        return {
            "cost_model_class": "ZeroCostModel",
            "fee_rate": "0",
            "slippage_rate": "0",
            "spread_rate": "0",
        }


class FeeSlippageSpreadModel(CostModel):
    """Cost model with proportional fee, slippage and spread components.

    All rates are fractions of notional (e.g. 0.001 = 0.1%). Total round-trip
    cost is applied once per completed setup as an informational estimate.
    """

    def __init__(
        self,
        fee_rate: Decimal = ZERO,
        slippage_rate: Decimal = ZERO,
        spread_rate: Decimal = ZERO,
    ):
        for name, rate in (
            ("fee_rate", fee_rate),
            ("slippage_rate", slippage_rate),
            ("spread_rate", spread_rate),
        ):
            if not isinstance(rate, Decimal):
                rate = Decimal(str(rate))
            if rate < ZERO:
                raise ValueError(f"{name} cannot be negative")
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.spread_rate = spread_rate

    def estimate_cost(self, notional: Decimal) -> Decimal:
        if notional < ZERO:
            raise ValueError("notional cannot be negative")
        rate = self.fee_rate + self.slippage_rate + self.spread_rate
        return notional * rate

    def describe(self) -> dict:
        return {
            "cost_model_class": "FeeSlippageSpreadModel",
            "fee_rate": str(self.fee_rate),
            "slippage_rate": str(self.slippage_rate),
            "spread_rate": str(self.spread_rate),
        }


def build_cost_model(
    fee: Optional[Decimal] = None,
    slippage: Optional[Decimal] = None,
    spread: Optional[Decimal] = None,
) -> CostModel:
    """Build a cost model; returns ZeroCostModel when all rates are zero/None."""
    rates = [r for r in (fee, slippage, spread) if r is not None]
    if not rates or all(Decimal(str(r)) == ZERO for r in rates):
        return ZeroCostModel()
    return FeeSlippageSpreadModel(
        fee_rate=Decimal(str(fee or 0)),
        slippage_rate=Decimal(str(slippage or 0)),
        spread_rate=Decimal(str(spread or 0)),
    )
