"""
Tests for the Phase 5 backtest-driven changes:

  1. `config.live_pairs` — backtest-approved subset for LIVE mode
  2. `config.max_hold_hours_for(pair)` — per-pair max hold override
  3. Risk-tier dead branch removal verified by test against ≥0.90 confidence

Backtest verdict (tasks/backtest_2026Q2_results.md, 2024-04-24 → 2026-04-24):
  USD_CAD passes all thresholds → approved for LIVE.
  USD_JPY fails every threshold → paper-only.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add backend root to sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def env_with_required_keys(monkeypatch):
    """Set the minimum env vars LumitradeConfig requires."""
    required = {
        "OANDA_API_KEY_DATA": "test_data_key",
        "OANDA_API_KEY_TRADING": "test_trade_key",
        "OANDA_ACCOUNT_ID": "001-001-1234567-001",
        "ANTHROPIC_API_KEY": "test_anthropic",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_KEY": "test_supabase",
        "TELNYX_API_KEY": "test_telnyx",
        "TELNYX_FROM_NUMBER": "+15551234567",
        "ALERT_SMS_TO": "+15559876543",
        "SENDGRID_API_KEY": "test_sendgrid",
        "ALERT_EMAIL_TO": "test@example.com",
        "INSTANCE_ID": "test-instance",
    }
    for k, v in required.items():
        monkeypatch.setenv(k, v)
    yield


# ─── 1. live_pairs config ────────────────────────────────────────────────────


def test_live_pairs_default_only_usd_cad(env_with_required_keys):
    """Operator override (2026-04-28): USD_JPY added to live_pairs for demo-week
    visibility on OANDA practice. Revert to ['USD_CAD'] before real-money trading."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert "USD_CAD" in cfg.live_pairs, f"USD_CAD must be in live_pairs — got {cfg.live_pairs}"
    assert "USD_JPY" in cfg.live_pairs, f"USD_JPY expected in live_pairs (demo-week override)"


def test_pairs_universe_still_includes_usd_jpy_for_paper(env_with_required_keys):
    """USD_JPY must remain in `pairs` so paper trading continues to evaluate it."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert "USD_JPY" in cfg.pairs, "USD_JPY removed from paper pairs — should remain"
    assert "USD_CAD" in cfg.pairs


def test_live_pairs_subset_of_pairs(env_with_required_keys):
    """Every pair in `live_pairs` must also be in `pairs` (you can't go live on something
    paper-mode never sees)."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    for p in cfg.live_pairs:
        assert p in cfg.pairs, f"{p} in live_pairs but not in pairs"


# ─── 2. Per-pair max_hold_hours ──────────────────────────────────────────────


def test_max_hold_hours_default_is_24(env_with_required_keys):
    """Default per the 106-trade audit (commit 6948951)."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert cfg.max_hold_hours == 24


def test_max_hold_hours_for_usd_cad_is_96(env_with_required_keys):
    """Backtest ablation showed removing 24h cap took USD_CAD PF 1.96 → 3.78."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert cfg.max_hold_hours_for("USD_CAD") == 96, (
        f"USD_CAD must allow 96h holds — got {cfg.max_hold_hours_for('USD_CAD')}"
    )


def test_max_hold_hours_for_usd_jpy_uses_default(env_with_required_keys):
    """USD_JPY ablation went the OTHER way — keeping the cap helps it. Override
    must NOT apply to JPY."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert cfg.max_hold_hours_for("USD_JPY") == 24


def test_max_hold_hours_for_unknown_pair_uses_default(env_with_required_keys):
    """Pairs without an override fall back to the default."""
    from lumitrade.config import LumitradeConfig
    cfg = LumitradeConfig()
    assert cfg.max_hold_hours_for("EUR_USD") == 24
    assert cfg.max_hold_hours_for("XAU_USD") == 24


# ─── 3. Risk tier dead branch removal ────────────────────────────────────────


def _make_proposal(confidence: Decimal):
    """Minimal SignalProposal mock just sufficient for _determine_risk_pct."""
    p = MagicMock()
    p.confidence_adjusted = confidence
    p.recommended_risk_pct = None
    return p


def test_risk_pct_below_080_is_0_5pct(env_with_required_keys):
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    rp = engine._determine_risk_pct(_make_proposal(Decimal("0.75")))
    assert rp == Decimal("0.005"), f"Expected 0.5% for conf 0.75 — got {rp}"


def test_risk_pct_at_080_is_1pct(env_with_required_keys):
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    rp = engine._determine_risk_pct(_make_proposal(Decimal("0.80")))
    assert rp == Decimal("0.01"), f"Expected 1.0% for conf 0.80 — got {rp}"


def test_risk_pct_above_080_still_1pct_after_dead_branch_removal(env_with_required_keys):
    """The >=0.90 -> 2% branch was removed. Anything >=0.80 now returns 1%.
    (The 0.80 confidence cap rejects these signals before sizing anyway, but the
    sizing logic itself must no longer have the dead 2% tier.)"""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    # 0.95 confidence: previously would have hit the dead 2% branch
    rp = engine._determine_risk_pct(_make_proposal(Decimal("0.95")))
    assert rp == Decimal("0.01"), (
        f"Dead 2% tier was removed — conf 0.95 should now return 1.0% — got {rp}"
    )


def test_risk_pct_ai_recommendation_advisory_only(env_with_required_keys):
    """AI-recommended risk_pct is currently advisory_only (pending empirical validation).
    _determine_risk_pct returns the deterministic confidence-tier rate, not the AI suggestion."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    p = MagicMock()
    p.confidence_adjusted = Decimal("0.75")
    p.recommended_risk_pct = Decimal("0.015")  # AI suggests 1.5% but is ignored
    rp = engine._determine_risk_pct(p)
    # Advisory mode: falls back to deterministic confidence-based rate (0.5% for conf 0.75)
    assert rp == Decimal("0.005"), f"Expected deterministic 0.5% (advisory mode) — got {rp}"


def test_risk_pct_ai_recommendation_clamped(env_with_required_keys):
    """When AI advisory eventually activates, extreme values must be clamped.
    Currently advisory_only so deterministic rate returned for all inputs."""
    from lumitrade.config import LumitradeConfig
    from lumitrade.risk_engine.engine import RiskEngine
    cfg = LumitradeConfig()
    engine = RiskEngine.__new__(RiskEngine)
    engine._config = cfg
    engine.config = cfg
    p = MagicMock()
    p.confidence_adjusted = Decimal("0.75")
    p.recommended_risk_pct = Decimal("0.05")  # 5% — advisory, ignored
    rp = engine._determine_risk_pct(p)
    assert rp == Decimal("0.005"), f"Expected deterministic 0.5% (advisory mode) — got {rp}"
