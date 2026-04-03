"""
Lumitrade Chart Generator
===========================
Generates multi-timeframe candlestick chart images for Claude visual analysis.
Uses matplotlib + mplfinance to create a 3-panel PNG (H4/H1/M15) in memory.

Per Adaptive Trading Memory spec, System 2: Visual Chart Analysis.

Phase 0 behavior: Fully functional chart generation. If mplfinance is not
available, falls back to basic matplotlib candlestick rendering. If ANY error
occurs, returns empty bytes (never crashes the pipeline).
"""

import base64
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

import pandas as pd

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Try importing mplfinance; fall back gracefully
_HAS_MPLFINANCE = False
try:
    import mplfinance as mpf

    _HAS_MPLFINANCE = True
except ImportError:
    logger.info("mplfinance_not_available", fallback="matplotlib_basic")

# matplotlib is required either way
try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend — no GUI needed
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    _HAS_MATPLOTLIB = True
except ImportError:
    _HAS_MATPLOTLIB = False
    logger.warning("matplotlib_not_available", chart_generation="disabled")


# ── Dark theme colors matching Lumitrade trading terminal ──────────
COLORS = {
    "bg": "#0D1B2A",
    "surface": "#111D2E",
    "text": "#E0E0E0",
    "text_dim": "#8899AA",
    "candle_up": "#00C896",
    "candle_down": "#FF4D6A",
    "wick_up": "#00C896",
    "wick_down": "#FF4D6A",
    "ema_20": "#3D8EFF",
    "ema_50": "#FFB347",
    "ema_200": "#FF4D6A",
    "bb_upper": "#555577",
    "bb_lower": "#555577",
    "bb_fill": "#222244",
    "sr_line": "#FFB347",
    "rsi_line": "#3D8EFF",
    "rsi_overbought": "#FF4D6A",
    "rsi_oversold": "#00C896",
    "rsi_mid": "#555577",
    "grid": "#1A2A3A",
}

# Chart dimensions
CHART_WIDTH_INCHES = 8.0
CHART_HEIGHT_INCHES = 12.0
CHART_DPI = 100  # 800x1200 px


class ChartGenerator:
    """Generates multi-timeframe candlestick chart images for Claude vision."""

    def __init__(self) -> None:
        self._available = _HAS_MATPLOTLIB

    async def generate_chart(
        self,
        pair: str,
        candles_h4: list,
        candles_h1: list,
        candles_m15: list,
        indicators: dict,
    ) -> bytes:
        """
        Generate a 3-panel candlestick chart as PNG bytes.

        Panel 1 (top): H4 candles with EMA 20/50/200 + Bollinger Bands
        Panel 2 (middle): H1 candles with support/resistance lines
        Panel 3 (bottom): M15 candles with RSI subplot

        Args:
            pair: Currency pair (e.g., "EUR_USD")
            candles_h4: List of Candle objects for H4 timeframe
            candles_h1: List of Candle objects for H1 timeframe
            candles_m15: List of Candle objects for M15 timeframe
            indicators: Dict with indicator values (ema_20, ema_50, ema_200,
                        bb_upper, bb_mid, bb_lower, rsi_14, etc.)

        Returns:
            PNG bytes. Empty bytes on any failure.
        """
        if not self._available:
            logger.debug("chart_generation_skipped", reason="matplotlib_unavailable")
            return b""

        try:
            return self._render_chart(pair, candles_h4, candles_h1, candles_m15, indicators)
        except Exception as e:
            logger.error("chart_generation_failed", pair=pair, error=str(e))
            return b""

    def _render_chart(
        self,
        pair: str,
        candles_h4: list,
        candles_h1: list,
        candles_m15: list,
        indicators: dict,
    ) -> bytes:
        """Internal render — may raise on error; caller catches."""
        # Convert candle lists to DataFrames
        df_h4 = self._candles_to_dataframe(candles_h4, last_n=20)
        df_h1 = self._candles_to_dataframe(candles_h1, last_n=20)
        df_m15 = self._candles_to_dataframe(candles_m15, last_n=20)

        if df_h4.empty and df_h1.empty and df_m15.empty:
            logger.warning("chart_no_candle_data", pair=pair)
            return b""

        if _HAS_MPLFINANCE:
            return self._render_mplfinance(pair, df_h4, df_h1, df_m15, indicators)
        else:
            return self._render_basic_matplotlib(pair, df_h4, df_h1, df_m15, indicators)

    # ── DataFrame conversion ──────────────────────────────────────

    def _candles_to_dataframe(self, candles: list, last_n: int = 20) -> pd.DataFrame:
        """
        Convert Candle objects to a pandas DataFrame suitable for mplfinance.

        Columns: Open, High, Low, Close, Volume with DatetimeIndex.
        """
        if not candles:
            return pd.DataFrame()

        # Take the last N candles
        recent = candles[-last_n:]

        rows = []
        for c in recent:
            rows.append({
                "Date": c.time if isinstance(c.time, datetime) else pd.Timestamp(str(c.time)),
                "Open": float(c.open) if isinstance(c.open, Decimal) else float(c.open),
                "High": float(c.high) if isinstance(c.high, Decimal) else float(c.high),
                "Low": float(c.low) if isinstance(c.low, Decimal) else float(c.low),
                "Close": float(c.close) if isinstance(c.close, Decimal) else float(c.close),
                "Volume": int(c.volume) if c.volume else 0,
            })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df["Date"] = pd.to_datetime(df["Date"], utc=True)
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)
        return df

    # ── mplfinance renderer (preferred) ───────────────────────────

    def _render_mplfinance(
        self,
        pair: str,
        df_h4: pd.DataFrame,
        df_h1: pd.DataFrame,
        df_m15: pd.DataFrame,
        indicators: dict,
    ) -> bytes:
        """Render using mplfinance for professional candlestick charts."""
        fig, axes = plt.subplots(
            4, 1,
            figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES),
            gridspec_kw={"height_ratios": [3, 3, 2.5, 1]},
            facecolor=COLORS["bg"],
        )

        # Custom market colors for mplfinance
        mc = mpf.make_marketcolors(
            up=COLORS["candle_up"],
            down=COLORS["candle_down"],
            wick={"up": COLORS["wick_up"], "down": COLORS["wick_down"]},
            edge={"up": COLORS["candle_up"], "down": COLORS["candle_down"]},
            volume={"up": COLORS["candle_up"], "down": COLORS["candle_down"]},
        )
        style = mpf.make_mpf_style(
            marketcolors=mc,
            facecolor=COLORS["bg"],
            edgecolor=COLORS["grid"],
            gridcolor=COLORS["grid"],
            gridstyle="--",
            rc={
                "axes.labelcolor": COLORS["text_dim"],
                "xtick.color": COLORS["text_dim"],
                "ytick.color": COLORS["text_dim"],
            },
        )

        # ── Panel 1: H4 with EMA + Bollinger Bands ───────────────
        ax_h4 = axes[0]
        if not df_h4.empty:
            self._plot_candlesticks_mpf(ax_h4, df_h4, style, mc)
            self._overlay_emas(ax_h4, df_h4, indicators)
            self._overlay_bollinger(ax_h4, df_h4, indicators)
            ax_h4.set_title(
                f"{pair} H4 — Trend + EMAs + Bollinger",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        else:
            ax_h4.text(0.5, 0.5, "H4 data unavailable", transform=ax_h4.transAxes,
                       ha="center", va="center", color=COLORS["text_dim"], fontsize=12)
        self._style_axis(ax_h4)

        # ── Panel 2: H1 with support/resistance ──────────────────
        ax_h1 = axes[1]
        if not df_h1.empty:
            self._plot_candlesticks_mpf(ax_h1, df_h1, style, mc)
            sr_levels = self._find_support_resistance(df_h1)
            for level in sr_levels:
                ax_h1.axhline(
                    y=level, color=COLORS["sr_line"], linestyle="--",
                    linewidth=0.8, alpha=0.7,
                )
            ax_h1.set_title(
                f"{pair} H1 — Structure + S/R Levels",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        else:
            ax_h1.text(0.5, 0.5, "H1 data unavailable", transform=ax_h1.transAxes,
                       ha="center", va="center", color=COLORS["text_dim"], fontsize=12)
        self._style_axis(ax_h1)

        # ── Panel 3: M15 candlesticks ────────────────────────────
        ax_m15 = axes[2]
        if not df_m15.empty:
            self._plot_candlesticks_mpf(ax_m15, df_m15, style, mc)
            ax_m15.set_title(
                f"{pair} M15 — Entry Timing",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        else:
            ax_m15.text(0.5, 0.5, "M15 data unavailable", transform=ax_m15.transAxes,
                        ha="center", va="center", color=COLORS["text_dim"], fontsize=12)
        self._style_axis(ax_m15)

        # ── Panel 4: RSI subplot ─────────────────────────────────
        ax_rsi = axes[3]
        self._plot_rsi_panel(ax_rsi, indicators)
        self._style_axis(ax_rsi)

        fig.tight_layout(pad=1.5)

        # Render to bytes
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=CHART_DPI, facecolor=COLORS["bg"],
                    bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        png_bytes = buf.read()

        logger.info("chart_generated", pair=pair, size_bytes=len(png_bytes),
                     renderer="mplfinance")
        return png_bytes

    def _plot_candlesticks_mpf(
        self, ax: Any, df: pd.DataFrame, style: Any, mc: Any,
    ) -> None:
        """Plot candlesticks on a given axis using mplfinance."""
        # mplfinance plot onto existing axis
        mpf.plot(
            df, type="candle", style=style, ax=ax,
            warn_too_much_data=1000,
        )

    # ── Basic matplotlib renderer (fallback) ──────────────────────

    def _render_basic_matplotlib(
        self,
        pair: str,
        df_h4: pd.DataFrame,
        df_h1: pd.DataFrame,
        df_m15: pd.DataFrame,
        indicators: dict,
    ) -> bytes:
        """Fallback renderer using only matplotlib (no mplfinance)."""
        fig, axes = plt.subplots(
            4, 1,
            figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES),
            gridspec_kw={"height_ratios": [3, 3, 2.5, 1]},
            facecolor=COLORS["bg"],
        )

        # Panel 1: H4
        ax_h4 = axes[0]
        if not df_h4.empty:
            self._plot_candlesticks_basic(ax_h4, df_h4)
            self._overlay_emas(ax_h4, df_h4, indicators)
            self._overlay_bollinger(ax_h4, df_h4, indicators)
            ax_h4.set_title(
                f"{pair} H4 — Trend + EMAs + Bollinger",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        self._style_axis(ax_h4)

        # Panel 2: H1
        ax_h1 = axes[1]
        if not df_h1.empty:
            self._plot_candlesticks_basic(ax_h1, df_h1)
            sr_levels = self._find_support_resistance(df_h1)
            for level in sr_levels:
                ax_h1.axhline(
                    y=level, color=COLORS["sr_line"], linestyle="--",
                    linewidth=0.8, alpha=0.7,
                )
            ax_h1.set_title(
                f"{pair} H1 — Structure + S/R Levels",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        self._style_axis(ax_h1)

        # Panel 3: M15
        ax_m15 = axes[2]
        if not df_m15.empty:
            self._plot_candlesticks_basic(ax_m15, df_m15)
            ax_m15.set_title(
                f"{pair} M15 — Entry Timing",
                color=COLORS["text"], fontsize=11, fontweight="bold", loc="left",
            )
        self._style_axis(ax_m15)

        # Panel 4: RSI
        ax_rsi = axes[3]
        self._plot_rsi_panel(ax_rsi, indicators)
        self._style_axis(ax_rsi)

        fig.tight_layout(pad=1.5)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=CHART_DPI, facecolor=COLORS["bg"],
                    bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        png_bytes = buf.read()

        logger.info("chart_generated", pair=pair, size_bytes=len(png_bytes),
                     renderer="matplotlib_basic")
        return png_bytes

    def _plot_candlesticks_basic(self, ax: Any, df: pd.DataFrame) -> None:
        """Draw candlesticks using matplotlib rectangles (no mplfinance)."""
        ax.set_facecolor(COLORS["bg"])

        # Convert index to numeric for plotting
        x_values = list(range(len(df)))
        width = 0.6

        for i, (idx, row) in enumerate(df.iterrows()):
            open_price = row["Open"]
            close_price = row["Close"]
            high_price = row["High"]
            low_price = row["Low"]

            is_up = close_price >= open_price
            color = COLORS["candle_up"] if is_up else COLORS["candle_down"]
            body_bottom = min(open_price, close_price)
            body_height = abs(close_price - open_price)

            # Wick (high-low line)
            ax.plot(
                [i, i], [low_price, high_price],
                color=color, linewidth=0.8,
            )
            # Body (rectangle)
            rect = Rectangle(
                (i - width / 2, body_bottom), width, body_height if body_height > 0 else 0.00001,
                facecolor=color, edgecolor=color, linewidth=0.5,
            )
            ax.add_patch(rect)

        ax.set_xlim(-1, len(df))
        if len(df) > 0:
            ax.set_ylim(
                df["Low"].min() * 0.9998,
                df["High"].max() * 1.0002,
            )

        # Format x-axis with date labels
        if len(df) > 0:
            tick_positions = list(range(0, len(df), max(1, len(df) // 5)))
            tick_labels = [df.index[i].strftime("%m/%d %H:%M") for i in tick_positions]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels, fontsize=7)

    # ── Overlays ──────────────────────────────────────────────────

    def _overlay_emas(self, ax: Any, df: pd.DataFrame, indicators: dict) -> None:
        """Overlay EMA 20/50/200 lines computed from the DataFrame."""
        if len(df) < 3:
            return

        x_values = list(range(len(df)))

        # Compute EMAs from candle data for the chart
        close_series = df["Close"]

        for span, color, label in [
            (20, COLORS["ema_20"], "EMA 20"),
            (50, COLORS["ema_50"], "EMA 50"),
            (200, COLORS["ema_200"], "EMA 200"),
        ]:
            if len(close_series) >= min(span, len(close_series)):
                ema = close_series.ewm(span=min(span, len(close_series)), adjust=False).mean()
                ax.plot(x_values, ema.values, color=color, linewidth=1.0,
                        alpha=0.8, label=label)

        ax.legend(
            loc="upper left", fontsize=7, framealpha=0.3,
            facecolor=COLORS["surface"], edgecolor=COLORS["grid"],
            labelcolor=COLORS["text_dim"],
        )

    def _overlay_bollinger(self, ax: Any, df: pd.DataFrame, indicators: dict) -> None:
        """Overlay Bollinger Bands computed from candle data."""
        if len(df) < 5:
            return

        x_values = list(range(len(df)))
        close_series = df["Close"]

        period = min(20, len(close_series))
        mid = close_series.rolling(window=period).mean()
        std = close_series.rolling(window=period).std()
        upper = mid + 2 * std
        lower = mid - 2 * std

        ax.plot(x_values, upper.values, color=COLORS["bb_upper"],
                linewidth=0.6, alpha=0.5)
        ax.plot(x_values, lower.values, color=COLORS["bb_lower"],
                linewidth=0.6, alpha=0.5)
        ax.fill_between(
            x_values, upper.values, lower.values,
            color=COLORS["bb_fill"], alpha=0.15,
        )

    # ── Support / Resistance detection ────────────────────────────

    def _find_support_resistance(self, df: pd.DataFrame) -> list[float]:
        """
        Find swing highs and swing lows from candle data.

        Swing high: candle.high > prev.high AND candle.high > next.high
        Swing low: candle.low < prev.low AND candle.low < next.low
        """
        levels: list[float] = []
        if len(df) < 3:
            return levels

        highs = df["High"].values
        lows = df["Low"].values

        for i in range(1, len(df) - 1):
            # Swing high
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                levels.append(float(highs[i]))
            # Swing low
            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                levels.append(float(lows[i]))

        # Deduplicate levels that are very close (within 0.05%)
        if levels:
            levels.sort()
            deduped = [levels[0]]
            for level in levels[1:]:
                if abs(level - deduped[-1]) / deduped[-1] > 0.0005:
                    deduped.append(level)
            levels = deduped

        logger.debug("support_resistance_found", count=len(levels))
        return levels

    # ── RSI panel ─────────────────────────────────────────────────

    def _plot_rsi_panel(self, ax: Any, indicators: dict) -> None:
        """Plot RSI value as a horizontal indicator bar."""
        ax.set_facecolor(COLORS["bg"])

        rsi_value = None
        if hasattr(indicators, "rsi_14"):
            rsi_value = float(indicators.rsi_14)
        elif isinstance(indicators, dict):
            rsi_value = float(indicators.get("rsi_14", 0))

        if rsi_value is None or rsi_value == 0:
            ax.text(0.5, 0.5, "RSI data unavailable", transform=ax.transAxes,
                    ha="center", va="center", color=COLORS["text_dim"], fontsize=10)
            return

        # Draw RSI zones
        ax.axhspan(70, 100, color=COLORS["rsi_overbought"], alpha=0.1)
        ax.axhspan(0, 30, color=COLORS["rsi_oversold"], alpha=0.1)
        ax.axhline(y=70, color=COLORS["rsi_overbought"], linestyle="--",
                    linewidth=0.6, alpha=0.5)
        ax.axhline(y=30, color=COLORS["rsi_oversold"], linestyle="--",
                    linewidth=0.6, alpha=0.5)
        ax.axhline(y=50, color=COLORS["rsi_mid"], linestyle=":",
                    linewidth=0.4, alpha=0.3)

        # Plot RSI as a single point with label
        ax.plot([0.5], [rsi_value], "o", color=COLORS["rsi_line"],
                markersize=10)
        ax.text(0.5, rsi_value + 5, f"RSI: {rsi_value:.1f}",
                ha="center", va="bottom", color=COLORS["rsi_line"],
                fontsize=10, fontweight="bold")

        ax.set_ylim(0, 100)
        ax.set_xlim(0, 1)
        ax.set_title(
            "RSI(14)", color=COLORS["text"], fontsize=10,
            fontweight="bold", loc="left",
        )
        ax.set_xticks([])

    # ── Axis styling ──────────────────────────────────────────────

    def _style_axis(self, ax: Any) -> None:
        """Apply dark theme styling to an axis."""
        ax.set_facecolor(COLORS["bg"])
        ax.tick_params(colors=COLORS["text_dim"], labelsize=7)
        ax.spines["top"].set_color(COLORS["grid"])
        ax.spines["bottom"].set_color(COLORS["grid"])
        ax.spines["left"].set_color(COLORS["grid"])
        ax.spines["right"].set_color(COLORS["grid"])
        ax.yaxis.label.set_color(COLORS["text_dim"])
        ax.xaxis.label.set_color(COLORS["text_dim"])
        ax.grid(True, color=COLORS["grid"], linestyle="--", linewidth=0.3, alpha=0.5)


def encode_chart_base64(png_bytes: bytes) -> str:
    """Encode PNG bytes to base64 string for Claude API."""
    if not png_bytes:
        return ""
    return base64.b64encode(png_bytes).decode("ascii")
