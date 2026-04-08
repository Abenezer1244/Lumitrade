"""
TradingView Chart Screenshotter
=================================
Screenshots TradingView's Advanced Chart widget using Playwright headless browser.
Produces PNG images that Claude Vision can analyze — TradingView's professional
chart rendering is what Claude was trained on, yielding better pattern recognition
than matplotlib-generated charts.

The widgetembed endpoint is a public embed URL with no anti-bot protections
(designed for third-party iframe embedding). No login required.

Fallback: returns empty bytes if Playwright or PIL is unavailable. Never crashes.
"""

import asyncio
from io import BytesIO

from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

# Guard imports — module is importable even without playwright/PIL
_HAS_PLAYWRIGHT = False
_HAS_PIL = False

try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    logger.warning("playwright_import_failed", reason="playwright package not installed")

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    logger.info("pil_not_available", fallback="single_panel_only")


# TradingView widget URL template — public, no login required
# Studies: EMA 20/50/200, Bollinger Bands, RSI
_TV_URL_TEMPLATE = (
    "https://s.tradingview.com/widgetembed/"
    "?symbol=OANDA%3A{symbol}"
    "&interval={interval}"
    "&theme=dark"
    "&style=1"
    "&locale=en"
    "&hide_top_toolbar=0"
    "&hide_legend=0"
    "&save_image=0"
    "&studies=MAExp%40tv-basicstudies%2120"
    "&studies=MAExp%40tv-basicstudies%2150"
    "&studies=MAExp%40tv-basicstudies%21200"
    "&studies=BB%40tv-basicstudies"
    "&studies=RSI%40tv-basicstudies"
)

# OANDA pair format (USD_JPY) → TradingView format (USDJPY)
_INTERVAL_MAP = {
    "H4": "240",
    "H1": "60",
    "M15": "15",
    "240": "240",
    "60": "60",
    "15": "15",
}

# Realistic user agent — avoids detection as headless
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _oanda_to_tv(pair: str) -> str:
    """Convert OANDA pair format to TradingView: USD_JPY → USDJPY."""
    return pair.replace("_", "")


class TVChartScreenshotter:
    """Screenshots TradingView charts using a reusable headless browser."""

    _instance = None
    _pw = None
    _browser = None
    _context = None

    @classmethod
    async def get_instance(cls) -> "TVChartScreenshotter":
        """Singleton — launch browser once, reuse across all screenshots."""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._launch()
        return cls._instance

    async def _launch(self) -> None:
        """Start headless Chromium with stealth settings and reusable context."""
        try:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-sandbox",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1200, "height": 800},
                user_agent=_USER_AGENT,
                locale="en-US",
            )
            logger.info("tv_screenshotter_launched")
        except Exception as e:
            logger.error("tv_screenshotter_launch_failed", error=str(e))
            self._browser = None

    async def screenshot(self, pair: str, interval: str = "60") -> bytes:
        """
        Screenshot a TradingView chart for the given pair and interval.

        Args:
            pair: OANDA format, e.g. "USD_JPY"
            interval: "240" (H4), "60" (H1), "15" (M15) or "H4", "H1", "M15"

        Returns:
            PNG bytes. Empty bytes on any failure.
        """
        if not _HAS_PLAYWRIGHT or self._browser is None:
            logger.warning(
                "tv_screenshot_unavailable",
                has_playwright=_HAS_PLAYWRIGHT,
                has_browser=self._browser is not None,
            )
            return b""

        tv_interval = _INTERVAL_MAP.get(interval, interval)
        tv_symbol = _oanda_to_tv(pair)
        url = _TV_URL_TEMPLATE.format(symbol=tv_symbol, interval=tv_interval)

        page = None
        try:
            page = await self._context.new_page()

            # Navigate with generous timeout for Docker environments
            await page.goto(url, wait_until="networkidle", timeout=25000)

            # Wait for the chart canvas to render
            await page.wait_for_selector("canvas", timeout=15000)

            # Wait for loading spinner to disappear (chart data loaded)
            try:
                await page.wait_for_function(
                    "() => !document.querySelector('.tv-spinner')",
                    timeout=10000,
                )
            except Exception:
                pass  # Spinner may not exist — continue

            # Extra settle time for indicators to finish drawing
            await asyncio.sleep(3)

            png_bytes = await page.screenshot(type="png", full_page=False)

            logger.info(
                "tv_chart_screenshot_taken",
                pair=pair,
                interval=tv_interval,
                size_kb=len(png_bytes) // 1024,
            )
            return png_bytes

        except Exception as e:
            logger.warning(
                "tv_chart_screenshot_failed",
                pair=pair,
                interval=tv_interval,
                error=str(e),
            )
            return b""

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def close(self) -> None:
        """Clean up browser resources."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
            logger.info("tv_screenshotter_closed")
        except Exception as e:
            logger.warning("tv_screenshotter_close_error", error=str(e))
        finally:
            TVChartScreenshotter._instance = None
            TVChartScreenshotter._browser = None
            TVChartScreenshotter._context = None


async def generate_tv_chart(
    pair: str,
    intervals: list[str] | None = None,
) -> bytes:
    """
    Screenshot multiple TradingView timeframes and composite into a single image.

    Args:
        pair: OANDA pair format, e.g. "USD_JPY"
        intervals: List of intervals, default ["240", "60", "15"] (H4, H1, M15)

    Returns:
        Combined PNG bytes (vertically stacked). Empty bytes on failure.
    """
    if not _HAS_PLAYWRIGHT:
        logger.warning("tv_chart_skipped", reason="playwright_not_installed")
        return b""

    if intervals is None:
        intervals = ["240", "60", "15"]

    try:
        screenshotter = await TVChartScreenshotter.get_instance()

        if screenshotter._browser is None:
            logger.warning("tv_chart_skipped", reason="browser_launch_failed")
            return b""

        # Screenshot all timeframes
        screenshots: list[bytes] = []
        for interval in intervals:
            png = await screenshotter.screenshot(pair, interval)
            if png:
                screenshots.append(png)
            else:
                logger.info("tv_chart_panel_empty", pair=pair, interval=interval)

        if not screenshots:
            logger.warning("tv_chart_all_panels_empty", pair=pair)
            return b""

        # If only one screenshot or PIL unavailable, return the first one
        if len(screenshots) == 1 or not _HAS_PIL:
            return screenshots[0]

        # Composite vertically using PIL
        images = [Image.open(BytesIO(s)) for s in screenshots]
        total_height = sum(img.height for img in images)
        max_width = max(img.width for img in images)

        composite = Image.new("RGB", (max_width, total_height))
        y_offset = 0
        for img in images:
            composite.paste(img, (0, y_offset))
            y_offset += img.height

        output = BytesIO()
        composite.save(output, format="PNG", optimize=True)
        png_bytes = output.getvalue()

        logger.info(
            "tv_chart_composite_ready",
            pair=pair,
            panels=len(screenshots),
            size_kb=len(png_bytes) // 1024,
        )
        return png_bytes

    except Exception as e:
        logger.warning("tv_chart_composite_failed", pair=pair, error=str(e))
        return b""
