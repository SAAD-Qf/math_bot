"""
Unit tests for the mathematical engine.
"""

from decimal import Decimal

import pytest

from tradingbot.exceptions import TradingBotError
from tradingbot.mathematical_engine import MathematicalCalculationResult, MathematicalEngine


def test_formula_canonical_example():
    """MANDATORY: A=100, B=150, C=125 -> B+C=275, TARGET=2.75."""
    engine = MathematicalEngine()
    result = engine.calculate_target(Decimal("100"), Decimal("150"), Decimal("125"))
    assert result.a == Decimal("100")
    assert result.b == Decimal("150")
    assert result.c == Decimal("125")
    assert result.sum == Decimal("275")
    assert result.target == Decimal("2.75")
    assert result.formula == "(B + C) / A"


def test_formula_not_multiplied_and_not_averaged():
    """Guard against formula corruption: (B*C)/A and (B+C)/2 must differ."""
    engine = MathematicalEngine()
    r = engine.calculate_target(100, 150, 125)
    assert r.target != (Decimal(150) * Decimal(125)) / Decimal(100)
    assert r.target != (Decimal(150) + Decimal(125)) / 2


def test_a_zero_raises():
    with pytest.raises(TradingBotError, match="Point A cannot be zero"):
        MathematicalEngine().calculate_target(0, 100, 100)


def test_negative_a_strict_mode_raises():
    with pytest.raises(TradingBotError, match="Point A cannot be negative"):
        MathematicalEngine(strict_mode=True).calculate_target(-100, 100, 100)


def test_negative_b_raises():
    with pytest.raises(TradingBotError, match="Point B must be positive"):
        MathematicalEngine().calculate_target(100, -5, 100)


def test_zero_b_raises():
    with pytest.raises(TradingBotError, match="Point B must be positive"):
        MathematicalEngine().calculate_target(100, 0, 100)


def test_zero_c_raises():
    with pytest.raises(TradingBotError, match="Point C must be positive"):
        MathematicalEngine().calculate_target(100, 100, 0)


def test_nan_a_raises():
    with pytest.raises(TradingBotError, match="cannot be NaN"):
        MathematicalEngine().calculate_target(Decimal("NaN"), 100, 100)


def test_nan_c_raises():
    with pytest.raises(TradingBotError, match="cannot be NaN"):
        MathematicalEngine().calculate_target(100, 100, Decimal("NaN"))


def test_infinity_raises():
    with pytest.raises(TradingBotError, match="cannot be infinite"):
        MathematicalEngine().calculate_target(Decimal("Infinity"), 100, 100)
    with pytest.raises(TradingBotError, match="cannot be infinite"):
        MathematicalEngine().calculate_target(100, Decimal("-Infinity"), 100)


def test_invalid_types_rejected():
    engine = MathematicalEngine()
    with pytest.raises(TradingBotError, match="must be numeric"):
        engine.calculate_target(None, 100, 100)
    with pytest.raises(TradingBotError, match="must be numeric"):
        engine.calculate_target(100, [1, 2], 100)
    with pytest.raises(TradingBotError, match="is not a valid number"):
        engine.calculate_target(100, 100, "abc")
    with pytest.raises(TradingBotError, match="got bool"):
        engine.calculate_target(True, 100, 100)

def test_numeric_string_and_float_inputs_coerced():
    engine = MathematicalEngine()
    result = engine.calculate_target("100", 150.0, 125)
    assert result.target == Decimal("2.75")


def test_precision_maintained_repeating_decimal():
    engine = MathematicalEngine()
    result = engine.calculate_target(3, 1, 1)
    assert result.target == Decimal(2) / Decimal(3)
    # 28 significant digits by default
    assert len(result.target.as_tuple().digits) <= 28


def test_precision_context_configurable():
    engine = MathematicalEngine(precision=8)
    result = engine.calculate_target(7, 10, 1)
    # (10 + 1) / 7 = 11/7 at 8 significant digits
    assert str(result.target).startswith("1.5714286")


def test_example_calculation_helper():
    result = MathematicalEngine().get_example_calculation()
    assert result.target == Decimal("2.75")


def test_validate_inputs_bool():
    engine = MathematicalEngine()
    assert engine.validate_inputs(100, 150, 125) is True
    assert engine.validate_inputs(0, 150, 125) is False
    assert engine.validate_inputs("x", 150, 125) is False


def test_calculate_from_points_uses_value_attribute():
    from tradingbot.domain import PricePoint

    engine = MathematicalEngine()
    result = engine.calculate_from_points(
        PricePoint(value=Decimal(100)),
        PricePoint(value=Decimal(150)),
        PricePoint(value=Decimal(125)),
    )
    assert result.target == Decimal("2.75")


def test_result_validation_roundtrip():
    engine = MathematicalEngine()
    result = engine.calculate_target(100, 150, 125)
    assert engine.validate_calculation_result(result) is True


def test_result_to_dict_strings():
    result = MathematicalEngine().calculate_target(100, 150, 125)
    d = result.to_dict()
    assert d["sum"] == "275"
    assert d["target"] == "2.75"
    assert d["formula"] == "(B + C) / A"


def test_result_post_init_rejects_zero_a():
    with pytest.raises(TradingBotError):
        MathematicalCalculationResult(
            a=Decimal(0), b=Decimal(1), c=Decimal(1),
            sum=Decimal(2), target=Decimal(2),
        )
