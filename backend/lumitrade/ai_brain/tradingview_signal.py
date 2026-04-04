"""
Lumitrade TradingView Signal
==============================
Fetches TradingView's 26-indicator technical analysis consensus
for a forex pair. Used as an additional confirmation layer.
"""

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Map OANDA pair names to TradingView symbols
PAIR_MAP = {
    "USD_JPY": "USDJPY",
    "USD_CAD": "USDCAD",
    "AUD_USD": "AUDUSD",
    "NZD_USD": "NZDUSD",
    "EUR_USD": "EURUSD",
    "GBP_USD": "GBPUSD",
    "USD_CHF": "USDCHF",
}


class TradingViewSignal:
    """Fetches TradingView consensus recommendation for forex pairs."""

    async def get_recommendation(self, pair: str) -> dict:
        """
        Get TradingView's recommendation for a pair.
        Returns dict with recommendation, buy/sell/neutral counts.
        Returns empty dict on any error — never crashes the pipeline.
        """
        tv_symbol = PAIR_MAP.get(pair)
        if not tv_symbol:
            return {}

        try:
            from tradingview_ta import TA_Handler, Interval

            handler = TA_Handler(
                symbol=tv_symbol,
                screener="forex",
                exchange="FX_IDC",
                interval=Interval.INTERVAL_1_HOUR,
            )
            analysis = handler.get_analysis()

            result = {
                "recommendation": analysis.summary["RECOMMENDATION"],
                "buy_signals": analysis.summary["BUY"],
                "sell_signals": analysis.summary["SELL"],
                "neutral_signals": analysis.summary["NEUTRAL"],
                "oscillators": analysis.oscillators["RECOMMENDATION"],
                "moving_averages": analysis.moving_averages["RECOMMENDATION"],
            }

            logger.info(
                "tradingview_signal",
                pair=pair,
                recommendation=result["recommendation"],
                buy=result["buy_signals"],
                sell=result["sell_signals"],
            )
            return result

        except Exception as e:
            logger.warning("tradingview_signal_failed", pair=pair, error=str(e))
            return {}

    def conflicts_with_action(self, tv_data: dict, action: str) -> bool:
        """
        Check if TradingView's recommendation conflicts with the proposed action.
        Returns True if there's a strong conflict that should block the trade.

        Rules:
        - BUY proposed but TV says STRONG_SELL or SELL → conflict
        - SELL proposed but TV says STRONG_BUY or BUY → conflict
        - Anything else → no conflict
        """
        if not tv_data:
            return False

        rec = tv_data.get("recommendation", "")

        if action == "BUY" and rec in ("STRONG_SELL", "SELL"):
            return True
        if action == "SELL" and rec in ("STRONG_BUY", "BUY"):
            return True

        return False

    def format_for_prompt(self, tv_data: dict) -> str:
        """Format TradingView data for injection into Claude's prompt."""
        if not tv_data:
            return "TradingView data unavailable."

        return (
            f"TradingView Consensus: {tv_data['recommendation']} "
            f"(Buy:{tv_data['buy_signals']} Sell:{tv_data['sell_signals']} "
            f"Neutral:{tv_data['neutral_signals']}) | "
            f"Oscillators: {tv_data['oscillators']} | "
            f"Moving Averages: {tv_data['moving_averages']}"
        )
