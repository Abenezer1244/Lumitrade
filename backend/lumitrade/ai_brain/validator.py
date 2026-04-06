"""
Lumitrade AI Output Validator
================================
Validates raw Claude API JSON output before it enters the pipeline.
8-step validation: JSON parse, required fields, action enum, numeric bounds,
price logic, price sanity, RR ratio, text quality.
100% coverage required. Per BDS Section 5.2 + Addition Set 2D.
"""

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..core.enums import Action
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of AI output validation."""

    passed: bool
    data: dict | None = None
    reason: str = ""


REQUIRED_FIELDS = [
    "action",
    "confidence",
    "entry_price",
    "stop_loss",
    "take_profit",
    "summary",
    "reasoning",
    "timeframe_h4_score",
    "timeframe_h1_score",
    "timeframe_m15_score",
    "key_levels",
    "invalidation_level",
    "expected_duration",
]

# Optional fields with safe defaults (Addition Set 2D)
OPTIONAL_FIELDS_WITH_DEFAULTS: dict[str, object] = {
    "recommended_risk_pct": Decimal("0.01"),
    "risk_reasoning": "No risk reasoning provided.",
}


class AIOutputValidator:
    """Validates raw Claude API JSON output before it enters the pipeline."""

    def validate(self, raw: str, live_price: Decimal) -> ValidationResult:
        """
        Run full 8-step validation pipeline.
        Returns ValidationResult with passed=True and parsed data, or
        passed=False with reason string.
        """
        # Step 1: Parse JSON
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            return ValidationResult(False, reason=f"JSON parse failed: {e}")

        if not isinstance(data, dict):
            return ValidationResult(
                False,
                reason="Expected JSON object, got array or primitive",
            )

        # Step 2: Required fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                return ValidationResult(False, reason=f"Missing field: {field}")

        # Handle optional fields — use defaults if missing
        for field, default in OPTIONAL_FIELDS_WITH_DEFAULTS.items():
            if field not in data:
                data[field] = default

        # Step 3: Action enum
        if data["action"] not in [a.value for a in Action]:
            return ValidationResult(
                False, reason=f"Invalid action: {data['action']}"
            )

        # Step 4: Numeric bounds
        try:
            confidence = Decimal(str(data["confidence"]))
            entry = Decimal(str(data["entry_price"]))
            sl = Decimal(str(data["stop_loss"]))
            tp = Decimal(str(data["take_profit"]))
        except (InvalidOperation, TypeError, ValueError) as e:
            return ValidationResult(
                False, reason=f"Numeric conversion failed: {e}"
            )

        if not (Decimal("0") <= confidence <= Decimal("1")):
            return ValidationResult(
                False, reason=f"Confidence out of range: {confidence}"
            )

        # Step 5: Price logic consistency (only for BUY/SELL)
        # TP of 0 is valid — means "no fixed TP, trailing stop manages exit"
        action = data["action"]
        if action == "BUY":
            if sl >= entry:
                return ValidationResult(
                    False, reason="BUY: SL must be below entry"
                )
            if tp != Decimal("0") and tp <= entry:
                return ValidationResult(
                    False, reason="BUY: TP must be above entry (or 0 for no TP)"
                )
        elif action == "SELL":
            if sl <= entry:
                return ValidationResult(
                    False, reason="SELL: SL must be above entry"
                )
            if tp != Decimal("0") and tp >= entry:
                return ValidationResult(
                    False, reason="SELL: TP must be below entry (or 0 for no TP)"
                )

        # Step 6: Price sanity (entry vs live price)
        if action != "HOLD" and live_price > 0:
            deviation = abs(entry - live_price) / live_price
            if deviation > Decimal("0.005"):
                return ValidationResult(
                    False,
                    reason=(
                        f"Entry {entry} deviates "
                        f"{deviation:.4f} from live {live_price}"
                    ),
                )

        # Step 7: Risk/reward ratio (skip if TP=0, trailing stop mode)
        if action != "HOLD" and tp != Decimal("0"):
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else Decimal("0")
            if rr < Decimal("1.5"):
                return ValidationResult(
                    False, reason=f"RR ratio {rr:.2f} below minimum 1.5"
                )

        # Step 7b: Minimum pip distance — TP/SL must be far enough
        # from entry to survive broker spread. Prevents OANDA
        # TAKE_PROFIT_ON_FILL_LOSS rejections.
        if action != "HOLD":
            from ..utils.pip_math import pips_between
            pair = data.get("pair", "")
            tp_pips = abs(float(pips_between(entry, tp, pair)))
            sl_pips = abs(float(pips_between(entry, sl, pair)))
            try:
                from ..config import LumitradeConfig
                _cfg = LumitradeConfig()  # type: ignore[call-arg]
                min_tp_pips = 10.0 if "XAU" in pair else float(_cfg.min_tp_pips)
                min_sl_pips = 10.0 if "XAU" in pair else float(_cfg.min_sl_pips)
            except Exception:
                min_tp_pips = 10.0 if "XAU" in pair else 15.0
                min_sl_pips = 10.0 if "XAU" in pair else 15.0
            if tp != Decimal("0") and tp_pips < min_tp_pips:
                return ValidationResult(
                    False,
                    reason=f"TP too close to entry ({tp_pips:.1f} pips, min {min_tp_pips})",
                )
            if sl_pips < min_sl_pips:
                return ValidationResult(
                    False,
                    reason=f"SL too close to entry ({sl_pips:.1f} pips, min {min_sl_pips})",
                )

        # Step 8: Summary and reasoning quality
        if len(data.get("summary", "")) < 20:
            return ValidationResult(False, reason="Summary too short")
        if len(data.get("reasoning", "")) < 100:
            return ValidationResult(
                False, reason="Reasoning too short (min 100 chars)"
            )

        # Validate optional recommended_risk_pct bounds
        if "recommended_risk_pct" in data:
            try:
                rp = Decimal(str(data["recommended_risk_pct"]))
                if not (Decimal("0.0025") <= rp <= Decimal("0.02")):
                    data["recommended_risk_pct"] = Decimal("0.01")
                    logger.warning(
                        "recommended_risk_pct_out_of_bounds", value=str(rp)
                    )
            except (InvalidOperation, TypeError, ValueError):
                data["recommended_risk_pct"] = Decimal("0.01")

        logger.info(
            "ai_output_validated", action=action, confidence=str(confidence)
        )
        return ValidationResult(True, data=data)
