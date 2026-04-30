"""
Lumitrade Unit Tests -- Position Reconciler (REC-001 to REC-006)
=================================================================
Validates ghost/phantom trade detection and structured reporting.
Zero tolerance for undetected position discrepancies -- every mismatch
between DB and OANDA is a potential uncontrolled risk exposure.

Per QTS v2.0 Section 7.3.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from lumitrade.core.enums import ExitReason
from lumitrade.state.reconciler import PositionReconciler


def _make_db_trade(
    trade_id: str,
    broker_trade_id: str,
    pair: str = "EUR_USD",
    status: str = "OPEN",
) -> dict:
    """Build a minimal DB trade row matching the reconciler's field access."""
    return {
        "id": trade_id,
        "broker_trade_id": broker_trade_id,
        "pair": pair,
        "status": status,
    }


def _make_oanda_trade(
    trade_id: str,
    instrument: str = "EUR_USD",
    units: str = "1000",
    price: str = "1.10500",
) -> dict:
    """Build a minimal OANDA open trade dict matching the reconciler's field access."""
    return {
        "id": trade_id,
        "instrument": instrument,
        "currentUnits": units,
        "initialUnits": units,
        "price": price,
        "openTime": "2026-03-20T10:00:00.000000Z",
    }


def _make_reconciler(
    db_trades: list[dict] | None = None,
    oanda_trades: list[dict] | None = None,
) -> tuple[PositionReconciler, AsyncMock, AsyncMock, AsyncMock]:
    """
    Create a PositionReconciler with mocked DB, OANDA, and AlertService.

    Returns (reconciler, mock_db, mock_oanda, mock_alerts).
    """
    mock_db = AsyncMock()
    mock_db.select.return_value = db_trades if db_trades is not None else []
    mock_db.update.return_value = {}
    mock_db.insert.return_value = {}

    mock_oanda = AsyncMock()
    mock_oanda.get_open_trades.return_value = (
        oanda_trades if oanda_trades is not None else []
    )

    mock_alerts = AsyncMock()

    reconciler = PositionReconciler(mock_db, mock_oanda, mock_alerts)
    return reconciler, mock_db, mock_oanda, mock_alerts


@pytest.mark.unit
class TestPositionReconciler:
    """REC-001 to REC-006: Position reconciliation between DB and OANDA."""

    # -- REC-001: Matching positions ----------------------------------------

    @pytest.mark.asyncio
    async def test_rec001_matching_positions_all_matched(self):
        """REC-001: When DB and OANDA have the same trades, all are matched."""
        db_trades = [
            _make_db_trade("uuid-1", "OT-100", "EUR_USD"),
            _make_db_trade("uuid-2", "OT-200", "GBP_USD"),
        ]
        oanda_trades = [
            _make_oanda_trade("OT-100", "EUR_USD"),
            _make_oanda_trade("OT-200", "GBP_USD"),
        ]

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        result = await reconciler.reconcile()

        assert len(result["matched"]) == 2
        assert len(result["ghosts"]) == 0
        assert len(result["phantoms"]) == 0

        # Verify matched entries contain expected data
        matched_broker_ids = {m["broker_trade_id"] for m in result["matched"]}
        assert matched_broker_ids == {"OT-100", "OT-200"}

        # No alerts should have been fired
        mock_alerts.send_critical.assert_not_called()

        # No DB updates or inserts for matched trades
        mock_db.update.assert_not_called()
        mock_db.insert.assert_not_called()

    # -- REC-002: Ghost trade detected --------------------------------------

    @pytest.mark.asyncio
    async def test_rec002_ghost_trade_detected(self):
        """REC-002: Trade in DB but not on OANDA is detected as ghost."""
        db_trades = [
            _make_db_trade("uuid-1", "OT-100", "EUR_USD"),
        ]
        oanda_trades = []  # OANDA has no trades -- ghost

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        result = await reconciler.reconcile()

        assert len(result["ghosts"]) == 1
        assert len(result["matched"]) == 0
        assert len(result["phantoms"]) == 0

        ghost = result["ghosts"][0]
        assert ghost["trade_id"] == "uuid-1"
        assert ghost["broker_trade_id"] == "OT-100"
        assert ghost["pair"] == "EUR_USD"
        assert ghost["action"] == "marked_closed_unknown"
        assert "detected_at" in ghost

        # DB must have been updated to mark trade CLOSED
        mock_db.update.assert_called_once()
        update_args = mock_db.update.call_args
        assert update_args[0][0] == "trades"
        assert update_args[0][1] == {"id": "uuid-1"}
        update_data = update_args[0][2]
        assert update_data["status"] == "CLOSED"
        assert update_data["exit_reason"] == ExitReason.UNKNOWN.value
        assert "closed_at" in update_data

        # CRITICAL alert must have been sent
        mock_alerts.send_critical.assert_called_once()
        alert_msg = mock_alerts.send_critical.call_args[0][0]
        assert "GHOST TRADE" in alert_msg
        assert "OT-100" in alert_msg

    # -- REC-003: Phantom trade detected ------------------------------------

    @pytest.mark.asyncio
    async def test_rec003_phantom_trade_detected(self):
        """REC-003: Trade on OANDA but not in DB is detected as phantom."""
        db_trades = []  # DB has no trades
        oanda_trades = [
            _make_oanda_trade("OT-999", "GBP_USD", units="5000", price="1.27000"),
        ]

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        result = await reconciler.reconcile()

        assert len(result["phantoms"]) == 1
        assert len(result["matched"]) == 0
        assert len(result["ghosts"]) == 0

        phantom = result["phantoms"][0]
        assert phantom["broker_trade_id"] == "OT-999"
        assert phantom["instrument"] == "GBP_USD"
        assert phantom["units"] == "5000"
        assert phantom["action"] == "emergency_record_created"
        assert "detected_at" in phantom

        # DB must have an emergency insert
        mock_db.insert.assert_called_once()
        insert_args = mock_db.insert.call_args
        assert insert_args[0][0] == "trades"
        insert_data = insert_args[0][1]
        assert insert_data["broker_trade_id"] == "OT-999"
        assert insert_data["pair"] == "GBP_USD"
        assert insert_data["direction"] == "BUY"  # positive units -> BUY
        assert insert_data["position_size"] == "5000"
        assert insert_data["status"] == "OPEN"

        # CRITICAL alert must have been sent
        mock_alerts.send_critical.assert_called_once()
        alert_msg = mock_alerts.send_critical.call_args[0][0]
        assert "PHANTOM TRADE" in alert_msg
        assert "OT-999" in alert_msg

    # -- REC-004: Empty DB and empty OANDA ----------------------------------

    @pytest.mark.asyncio
    async def test_rec004_empty_db_and_oanda_clean(self):
        """REC-004: No trades on either side produces a clean reconciliation."""
        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades=[], oanda_trades=[]
        )
        result = await reconciler.reconcile()

        assert len(result["ghosts"]) == 0
        assert len(result["phantoms"]) == 0
        assert len(result["matched"]) == 0
        assert "reconciled_at" in result
        assert "error" not in result

        # No alerts, no DB mutations
        mock_alerts.send_critical.assert_not_called()
        mock_db.update.assert_not_called()
        mock_db.insert.assert_not_called()

    # -- REC-005: Mixed matches, ghosts, and phantoms -----------------------

    @pytest.mark.asyncio
    async def test_rec005_mixed_matches_ghosts_phantoms(self):
        """REC-005: Multiple trades with a mix of matched, ghost, and phantom."""
        db_trades = [
            _make_db_trade("uuid-1", "OT-100", "EUR_USD"),   # matched
            _make_db_trade("uuid-2", "OT-200", "GBP_USD"),   # ghost (not on OANDA)
            _make_db_trade("uuid-3", "OT-300", "USD_JPY"),   # matched
        ]
        oanda_trades = [
            _make_oanda_trade("OT-100", "EUR_USD"),           # matched
            _make_oanda_trade("OT-300", "USD_JPY"),           # matched
            _make_oanda_trade("OT-400", "AUD_USD", "-2000"),  # phantom (not in DB)
        ]

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        result = await reconciler.reconcile()

        # Verify counts
        assert len(result["matched"]) == 2
        assert len(result["ghosts"]) == 1
        assert len(result["phantoms"]) == 1

        # Verify ghost details
        ghost = result["ghosts"][0]
        assert ghost["broker_trade_id"] == "OT-200"
        assert ghost["pair"] == "GBP_USD"

        # Verify phantom details (negative units -> SELL)
        phantom = result["phantoms"][0]
        assert phantom["broker_trade_id"] == "OT-400"
        assert phantom["instrument"] == "AUD_USD"

        # Verify phantom direction is SELL (negative units)
        insert_data = mock_db.insert.call_args[0][1]
        assert insert_data["direction"] == "SELL"

        # Verify matched broker IDs
        matched_broker_ids = {m["broker_trade_id"] for m in result["matched"]}
        assert matched_broker_ids == {"OT-100", "OT-300"}

        # Two CRITICAL alerts: one for ghost, one for phantom
        assert mock_alerts.send_critical.call_count == 2

    # -- REC-006: Structured report with correct counts ---------------------

    @pytest.mark.asyncio
    async def test_rec006_structured_report_format(self):
        """REC-006: Reconciliation returns properly structured report."""
        db_trades = [
            _make_db_trade("uuid-1", "OT-100", "EUR_USD"),
            _make_db_trade("uuid-2", "OT-200", "GBP_USD"),
        ]
        oanda_trades = [
            _make_oanda_trade("OT-100", "EUR_USD"),
            _make_oanda_trade("OT-300", "USD_JPY"),
        ]

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        result = await reconciler.reconcile()

        # Verify top-level keys exist
        assert "ghosts" in result
        assert "phantoms" in result
        assert "matched" in result
        assert "reconciled_at" in result

        # Verify types
        assert isinstance(result["ghosts"], list)
        assert isinstance(result["phantoms"], list)
        assert isinstance(result["matched"], list)
        assert isinstance(result["reconciled_at"], str)

        # Verify reconciled_at is a valid ISO timestamp
        parsed_time = datetime.fromisoformat(result["reconciled_at"])
        assert parsed_time.tzinfo is not None

        # Verify counts: 1 matched (OT-100), 1 ghost (OT-200), 1 phantom (OT-300)
        assert len(result["matched"]) == 1
        assert len(result["ghosts"]) == 1
        assert len(result["phantoms"]) == 1

        # Verify matched entry structure
        match_entry = result["matched"][0]
        assert "trade_id" in match_entry
        assert "broker_trade_id" in match_entry
        assert "pair" in match_entry
        assert match_entry["broker_trade_id"] == "OT-100"

        # Verify ghost entry structure
        ghost_entry = result["ghosts"][0]
        assert "trade_id" in ghost_entry
        assert "broker_trade_id" in ghost_entry
        assert "pair" in ghost_entry
        assert "action" in ghost_entry
        assert "detected_at" in ghost_entry

        # Verify phantom entry structure
        phantom_entry = result["phantoms"][0]
        assert "broker_trade_id" in phantom_entry
        assert "instrument" in phantom_entry
        assert "units" in phantom_entry
        assert "action" in phantom_entry
        assert "detected_at" in phantom_entry

        # No error key in success case
        assert "error" not in result

    # -- REC-007: DB exception during reconcile produces error report -------

    @pytest.mark.asyncio
    async def test_rec007_db_exception_returns_error_report(self):
        """REC-007: If DB select raises, reconcile returns report with error flag."""
        mock_db = AsyncMock()
        mock_db.select.side_effect = Exception("DB connection lost")
        mock_oanda = AsyncMock()
        mock_alerts = AsyncMock()

        reconciler = PositionReconciler(mock_db, mock_oanda, mock_alerts)
        result = await reconciler.reconcile()

        assert result["error"] is True
        assert "reconciled_at" in result
        # Alert should be fired about the failure
        mock_alerts.send_critical.assert_called_once()
        alert_msg = mock_alerts.send_critical.call_args[0][0]
        assert "reconciliation failed" in alert_msg.lower()

    # -- REC-008: OANDA exception during reconcile produces error report ----

    @pytest.mark.asyncio
    async def test_rec008_oanda_exception_returns_error_report(self):
        """REC-008: If OANDA get_open_trades raises, reconcile handles gracefully."""
        mock_db = AsyncMock()
        mock_db.select.return_value = [
            _make_db_trade("uuid-1", "OT-100"),
        ]
        mock_oanda = AsyncMock()
        mock_oanda.get_open_trades.side_effect = Exception("OANDA timeout")
        mock_alerts = AsyncMock()

        reconciler = PositionReconciler(mock_db, mock_oanda, mock_alerts)
        result = await reconciler.reconcile()

        assert result["error"] is True
        mock_alerts.send_critical.assert_called_once()

    # -- REC-009: Ghost trade with DB update failure still reports ----------

    @pytest.mark.asyncio
    async def test_rec009_ghost_db_update_failure_still_alerts(self):
        """REC-009: If marking ghost as CLOSED fails, alert is still sent."""
        db_trades = [_make_db_trade("uuid-1", "OT-100", "EUR_USD")]
        oanda_trades = []

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades, oanda_trades
        )
        # Make the update call fail
        mock_db.update.side_effect = Exception("DB write failure")

        result = await reconciler.reconcile()

        # Ghost should still be reported even if DB update failed
        assert len(result["ghosts"]) == 1
        # Alert must still fire
        mock_alerts.send_critical.assert_called_once()

    # -- REC-010: Phantom with negative units detected as SELL -------------

    @pytest.mark.asyncio
    async def test_rec010_phantom_negative_units_is_sell(self):
        """REC-010: Phantom trade with negative units is classified as SELL."""
        oanda_trades = [
            _make_oanda_trade("OT-500", "USD_CHF", units="-3000"),
        ]

        reconciler, mock_db, mock_oanda, mock_alerts = _make_reconciler(
            db_trades=[], oanda_trades=oanda_trades
        )
        result = await reconciler.reconcile()

        assert len(result["phantoms"]) == 1
        insert_data = mock_db.insert.call_args[0][1]
        assert insert_data["direction"] == "SELL"
        assert insert_data["position_size"] == "3000"
