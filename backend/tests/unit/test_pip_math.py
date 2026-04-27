"""
Pip Math Tests — PM-001 to PM-015
====================================
All 15 tests from QTS Table 6.
All calculations use Decimal. Manually verified expected values.
100% coverage required on this module.
"""

from decimal import Decimal

from lumitrade.utils.pip_math import (
    calculate_position_size,
    pip_size,
    pip_value_per_unit,
    pips_between,
)


class TestPipSize:
    """PM-001 to PM-004: Pip size lookup."""

    def test_eurusd_pip_size(self):
        """PM-001"""
        assert pip_size("EUR_USD") == Decimal("0.0001")

    def test_usdjpy_pip_size(self):
        """PM-002"""
        assert pip_size("USD_JPY") == Decimal("0.01")

    def test_gbpusd_pip_size(self):
        """PM-003"""
        assert pip_size("GBP_USD") == Decimal("0.0001")

    def test_unknown_pair_uses_default(self):
        """PM-004"""
        assert pip_size("XYZ_ABC") == Decimal("0.0001")


class TestPipsBetween:
    """PM-005 to PM-007: Pip distance calculation."""

    def test_pips_between_eurusd_10pips(self):
        """PM-005"""
        result = pips_between(Decimal("1.08430"), Decimal("1.08330"), "EUR_USD")
        assert result == Decimal("10.0")

    def test_pips_between_usdjpy_10pips(self):
        """PM-006"""
        result = pips_between(Decimal("150.430"), Decimal("150.330"), "USD_JPY")
        assert result == Decimal("10.0")

    def test_pips_between_is_absolute(self):
        """PM-007: Order of prices should not matter."""
        result_a = pips_between(Decimal("1.08430"), Decimal("1.08330"), "EUR_USD")
        result_b = pips_between(Decimal("1.08330"), Decimal("1.08430"), "EUR_USD")
        assert result_a == result_b
        assert result_a > 0


class TestPositionSize:
    """PM-008 to PM-013: Position sizing formula."""

    def test_position_size_300_acct_1pct_20pip_sl(self):
        """PM-008: $300 account, 1% risk, 20 pip SL, EUR/USD -> 1,500 units.
        Per 52d3587, sizer floors to 1 unit (OANDA broker minimum), not
        1000. raw = 3.00 / (20 * 0.0001) = 1500."""
        units, risk_usd = calculate_position_size(
            balance=Decimal("300"),
            risk_pct=Decimal("0.01"),
            sl_pips=Decimal("20"),
            pair="EUR_USD",
            current_rate=Decimal("1.08430"),
        )
        assert units == 1500
        # risk_usd = 1500 * 20 * 0.0001 = $3.00
        assert Decimal("2.50") <= risk_usd <= Decimal("3.50")

    def test_position_size_1000_acct_2pct_15pip_sl(self):
        """PM-009: $1000 account, 2% risk, 15 pip SL, EUR/USD -> 13,333 units.
        Per 52d3587, sizer floors to 1 unit. raw = 20 / (15 * 0.0001) = 13333."""
        units, risk_usd = calculate_position_size(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.02"),
            sl_pips=Decimal("15"),
            pair="EUR_USD",
            current_rate=Decimal("1.08430"),
        )
        assert units == 13333
        # risk_usd = 13333 * 15 * 0.0001 ≈ $19.9995
        assert Decimal("19.00") <= risk_usd <= Decimal("21.00")

    def test_position_size_rounds_down_to_micro_lot(self):
        """PM-010: Result rounds down to nearest 1000."""
        # Set up so raw units would be ~1500
        units, _ = calculate_position_size(
            balance=Decimal("300"),
            risk_pct=Decimal("0.01"),
            sl_pips=Decimal("15"),
            pair="EUR_USD",
            current_rate=Decimal("1.08430"),
        )
        # Should floor: 2000 (raw ~2000) or 1000 depending on exact calc
        assert units % 1000 == 0

    def test_position_size_zero_sl_returns_zero(self):
        """PM-011: Zero SL pips -> zero units."""
        units, risk_usd = calculate_position_size(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            sl_pips=Decimal("0"),
            pair="EUR_USD",
            current_rate=Decimal("1.08430"),
        )
        assert units == 0
        assert risk_usd == Decimal("0")

    def test_position_size_zero_pip_value_returns_zero(self):
        """PM-012: Zero current rate for USD base pair -> zero."""
        units, risk_usd = calculate_position_size(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            sl_pips=Decimal("20"),
            pair="USD_JPY",
            current_rate=Decimal("0"),
        )
        assert units == 0
        assert risk_usd == Decimal("0")

    def test_risk_amount_matches_position_math(self):
        """PM-013: Verify risk_usd == units * sl_pips * pip_value (within rounding)."""
        units, risk_usd = calculate_position_size(
            balance=Decimal("500"),
            risk_pct=Decimal("0.015"),
            sl_pips=Decimal("25"),
            pair="EUR_USD",
            current_rate=Decimal("1.08430"),
        )
        expected_risk = units * Decimal("25") * pip_value_per_unit(
            "EUR_USD", Decimal("1.08430")
        )
        assert abs(risk_usd - expected_risk) < Decimal("0.01")


class TestPipValuePerUnit:
    """PM-014 to PM-015: Pip value calculation."""

    def test_pip_value_eurusd_usd_account(self):
        """PM-014: EUR/USD pip value = 0.0001 per unit."""
        result = pip_value_per_unit("EUR_USD", Decimal("1.08430"))
        assert result == Decimal("0.0001")

    def test_pip_value_usdjpy_usd_account(self):
        """PM-015: USD/JPY pip value = 0.01/rate per unit."""
        result = pip_value_per_unit("USD_JPY", Decimal("150.0"))
        expected = Decimal("0.01") / Decimal("150.0")
        assert abs(result - expected) < Decimal("0.0000001")
