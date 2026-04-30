"""
Position Sizer Unit Tests
============================
Per BDS Section 6.1 — verify position sizing with Decimal arithmetic,
micro lot rounding, and edge cases.
PS-001 through PS-008.
"""

from decimal import Decimal

import pytest

from lumitrade.risk_engine.position_sizer import PositionSizer


@pytest.mark.unit
class TestPositionSizer:
    """Test PositionSizer.calculate() with realistic forex scenarios."""

    @pytest.fixture
    def sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer()

    def test_ps_001_eur_usd_300_balance_1pct_20pip_sl(self, sizer):
        """PS-001: EUR/USD $300 balance, 1% risk, 20 pip SL.
        risk_usd = 300 * 0.01 = $3.00
        pip_value_per_unit for EUR_USD (quote=USD) = 0.0001
        raw_units = 3.00 / (20 * 0.0001) = 3.00 / 0.002 = 1500
        Per commit 52d3587, pip_math floors to 1 unit (OANDA broker
        minimum) — no more 1000-unit micro-lot rounding inside the
        sizer. Policy thresholds (meaningful risk, etc.) are enforced
        one layer up in risk_engine.
        """
        units, risk_usd = sizer.calculate(
            balance=Decimal("300"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0830"),
            pair="EUR_USD",
        )
        assert units == Decimal("1500")
        assert isinstance(units, Decimal)
        assert risk_usd > Decimal("0")
        # Actual risk = 1500 * 20 * 0.0001 = $3.00
        assert risk_usd == Decimal("3.0000")

    def test_ps_002_usd_jpy_1000_balance_2pct_15pip_sl(self, sizer):
        """PS-002: USD/JPY $1000 balance, 2% risk, 15 pip SL.
        risk_usd = 1000 * 0.02 = $20.00
        pip_value_per_unit for USD_JPY (base=USD) = 0.01 / rate
        At rate 150.00: pv = 0.01 / 150 = 0.00006667
        raw_units = 20.00 / (15 * 0.00006667) = 20.00 / 0.001 = 20000
        floored to 20000
        """
        units, risk_usd = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.02"),
            entry=Decimal("150.000"),
            stop_loss=Decimal("149.850"),
            pair="USD_JPY",
        )
        assert units >= 1000
        assert units % 1000 == 0
        assert isinstance(units, Decimal)
        assert risk_usd > Decimal("0")

    def test_ps_003_floors_to_nearest_unit(self, sizer):
        """PS-003: Units floored to nearest integer (1-unit broker
        minimum), not micro-lot. Old 1000-rounding behavior was removed
        in 52d3587 to allow small accounts to size correctly."""
        units, risk_usd = sizer.calculate(
            balance=Decimal("500"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0830"),
            pair="EUR_USD",
        )
        # risk = $5, sl = 20 pips, pv = 0.0001
        # raw = 5 / (20 * 0.0001) = 2500 -> floored to int = 2500
        assert units == Decimal("2500")
        assert isinstance(units, Decimal)

    def test_ps_004_zero_sl_returns_zero(self, sizer):
        """PS-004: When entry == stop_loss (0 pip SL), return (0, 0)."""
        units, risk_usd = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0850"),
            pair="EUR_USD",
        )
        assert units == Decimal("0")
        assert risk_usd == Decimal("0")

    def test_ps_005_small_balance_sizes_correctly(self, sizer):
        """PS-005: $50 account must produce a valid integer position.
        After 52d3587 the sizer floors to 1 unit, so small accounts no
        longer collapse to zero. Risk-engine policy gates decide whether
        the trade is meaningful (Gate B), not the sizer."""
        units, risk_usd = sizer.calculate(
            balance=Decimal("50"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0840"),
            pair="EUR_USD",
        )
        # risk = $0.50, sl = 10 pips, pv = 0.0001
        # raw = 0.50 / (10 * 0.0001) = 500 -> int = 500
        assert units == Decimal("500")
        assert isinstance(units, Decimal)
        assert risk_usd > Decimal("0")

    def test_ps_006_risk_amount_within_budget(self, sizer):
        """PS-006: Actual risk amount must be <= balance * risk_pct."""
        balance = Decimal("1000")
        risk_pct = Decimal("0.02")
        units, risk_usd = sizer.calculate(
            balance=balance,
            risk_pct=risk_pct,
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0820"),
            pair="EUR_USD",
        )
        max_risk = balance * risk_pct
        assert risk_usd <= max_risk, (
            f"Risk ${risk_usd} exceeds budget ${max_risk}"
        )

    def test_ps_007_gbp_usd_500_balance_05pct_25pip_sl(self, sizer):
        """PS-007: GBP/USD $500 balance, 0.5% risk, 25 pip SL.
        risk_usd = 500 * 0.005 = $2.50
        pip_value for GBP_USD (quote=USD) = 0.0001
        raw = 2.50 / (25 * 0.0001) = 2.50 / 0.0025 = 1000
        floored to 1000
        """
        units, risk_usd = sizer.calculate(
            balance=Decimal("500"),
            risk_pct=Decimal("0.005"),
            entry=Decimal("1.2650"),
            stop_loss=Decimal("1.2625"),
            pair="GBP_USD",
        )
        assert units == Decimal("1000")
        assert units % 1000 == 0
        # Actual risk = 1000 * 25 * 0.0001 = $2.50
        assert risk_usd == Decimal("2.5000")

    def test_ps_008_tight_sl_one_pip(self, sizer):
        """PS-008: Extremely tight 1-pip SL produces large position size."""
        units, risk_usd = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.02"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0849"),
            pair="EUR_USD",
        )
        # risk = $20, sl = 1 pip, pv = 0.0001
        # raw = 20 / (1 * 0.0001) = 200000 -> floored to 200000
        assert units == Decimal("200000")
        assert units % 1000 == 0
        assert isinstance(units, Decimal)

    def test_ps_return_types(self, sizer):
        """Verify return types are (Decimal, Decimal) as documented."""
        units, risk_usd = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0830"),
            pair="EUR_USD",
        )
        assert isinstance(units, Decimal)
        assert isinstance(risk_usd, Decimal)

    def test_ps_sell_direction_same_result(self, sizer):
        """SL above entry (SELL) should produce same size as SL below (BUY)
        with same pip distance."""
        units_buy, risk_buy = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0850"),
            stop_loss=Decimal("1.0830"),
            pair="EUR_USD",
        )
        units_sell, risk_sell = sizer.calculate(
            balance=Decimal("1000"),
            risk_pct=Decimal("0.01"),
            entry=Decimal("1.0830"),
            stop_loss=Decimal("1.0850"),
            pair="EUR_USD",
        )
        assert units_buy == units_sell
        assert risk_buy == risk_sell
