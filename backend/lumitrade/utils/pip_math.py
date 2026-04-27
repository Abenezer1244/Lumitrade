"""
Lumitrade Pip Math Utilities
==============================
All forex pip calculations. Decimal arithmetic only — never float.
Per BDS Section 10.1. All formulas verified against QTS test cases PM-001 to PM-015.
"""

from decimal import Decimal

# Pip sizes per currency pair
PIP_SIZE: dict[str, Decimal] = {
    "EUR_USD": Decimal("0.0001"),
    "GBP_USD": Decimal("0.0001"),
    "USD_JPY": Decimal("0.01"),
    "USD_CHF": Decimal("0.0001"),
    "AUD_USD": Decimal("0.0001"),
    "USD_CAD": Decimal("0.0001"),
    "NZD_USD": Decimal("0.0001"),
    "XAU_USD": Decimal("0.01"),
    "EUR_JPY": Decimal("0.01"),
    "GBP_JPY": Decimal("0.01"),
}
DEFAULT_PIP = Decimal("0.0001")


def pip_size(pair: str) -> Decimal:
    """Get the pip size for a currency pair."""
    return PIP_SIZE.get(pair, DEFAULT_PIP)


def pips_between(price_a: Decimal, price_b: Decimal, pair: str) -> Decimal:
    """Calculate absolute pip difference between two prices."""
    return abs(price_a - price_b) / pip_size(pair)


def pip_value_per_unit(pair: str, current_rate: Decimal) -> Decimal:
    """USD value of 1 pip movement for 1 unit of the pair."""
    ps = pip_size(pair)
    if pair.endswith("_USD"):
        # Quote currency is USD: pip value = pip_size
        return ps
    elif pair.startswith("USD_"):
        # Base currency is USD: pip value = pip_size / rate
        if current_rate == 0:
            return Decimal("0")
        return ps / current_rate
    else:
        # Cross pair: approximate via USD rate (simplified for Phase 0)
        return ps


def calculate_position_size(
    balance: Decimal,
    risk_pct: Decimal,
    sl_pips: Decimal,
    pair: str,
    current_rate: Decimal,
) -> tuple[int, Decimal]:
    """
    Calculate position size in units and risk amount in USD.
    Returns (units: int, risk_amount_usd: Decimal).
    Floors to nearest unit — OANDA minimum is 1 unit for all pairs.
    """
    risk_usd = balance * risk_pct
    pv_per_unit = pip_value_per_unit(pair, current_rate)

    if sl_pips == 0 or pv_per_unit == 0:
        return 0, Decimal("0")

    raw_units = risk_usd / (sl_pips * pv_per_unit)
    units = max(0, int(raw_units))  # Floor to nearest unit, never negative

    actual_risk = units * sl_pips * pv_per_unit
    return units, actual_risk
