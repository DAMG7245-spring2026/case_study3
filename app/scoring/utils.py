"""Task 5.1: Decimal utilities for financial-grade precision.

All score calculations in the PE Org-AI-R platform use Decimal arithmetic
to avoid floating-point accumulation errors.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List


def to_decimal(value: float, places: int = 4) -> Decimal:
    """Convert float to Decimal with explicit precision and ROUND_HALF_UP rounding.

    Args:
        value: Numeric value to convert.
        places: Number of decimal places to quantize to.

    Returns:
        Decimal with the specified precision.
    """
    if isinstance(value, Decimal):
        return value.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(
        Decimal(10) ** -places,
        rounding=ROUND_HALF_UP,
    )


def clamp(
    value: Decimal,
    min_val: Decimal = Decimal(0),
    max_val: Decimal = Decimal(100),
) -> Decimal:
    """Clamp a Decimal value to [min_val, max_val].

    Args:
        value: Value to clamp.
        min_val: Lower bound (default 0).
        max_val: Upper bound (default 100).

    Returns:
        Clamped Decimal.
    """
    return max(min_val, min(max_val, value))


def weighted_mean(values: List[Decimal], weights: List[Decimal]) -> Decimal:
    """Calculate the weighted mean of Decimal values.

    Args:
        values: List of dimension scores.
        weights: Corresponding weights (should sum to 1.0).

    Returns:
        Weighted mean, quantized to 4 decimal places.

    Raises:
        ValueError: If lengths differ.
    """
    if len(values) != len(weights):
        raise ValueError("Values and weights must have the same length")
    if not values:
        return Decimal(0)
    total = sum(v * w for v, w in zip(values, weights))
    return total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def weighted_std_dev(
    values: List[Decimal],
    weights: List[Decimal],
    mean: Decimal,
) -> Decimal:
    """Calculate the weighted standard deviation.

    Uses population std-dev formula:
        σ_w = sqrt( Σ w_i * (v_i - mean)^2 / Σ w_i )

    Args:
        values: List of scores.
        weights: Corresponding weights.
        mean: Pre-computed weighted mean (avoids recomputation).

    Returns:
        Weighted std deviation, quantized to 4 decimal places.
    """
    if len(values) != len(weights):
        raise ValueError("Values and weights must have the same length")
    if not values:
        return Decimal(0)
    total_weight = sum(weights)
    if total_weight == Decimal(0):
        return Decimal(0)
    variance = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_weight
    return variance.sqrt().quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def coefficient_of_variation(std_dev: Decimal, mean: Decimal) -> Decimal:
    """Calculate coefficient of variation with zero-division protection.

    cv = std_dev / mean   (if mean > 0, else 0)

    Args:
        std_dev: Standard deviation.
        mean: Mean value.

    Returns:
        CV as Decimal, quantized to 4 decimal places.
    """
    if mean == Decimal(0):
        return Decimal(0)
    return (std_dev / mean).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
