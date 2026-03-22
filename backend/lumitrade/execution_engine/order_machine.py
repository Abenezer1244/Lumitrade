"""
Lumitrade Order State Machine
================================
Tracks order lifecycle. Enforces state transitions. Rejects expired orders.
Per BDS and SAS specs.
"""
from datetime import datetime, timezone
from ..core.enums import OrderStatus
from ..core.models import ApprovedOrder
from ..core.exceptions import OrderExpiredError
from ..infrastructure.secure_logger import get_logger

logger = get_logger(__name__)

VALID_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.TIMEOUT},
    OrderStatus.SUBMITTED: {OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED, OrderStatus.TIMEOUT},
    OrderStatus.ACKNOWLEDGED: {OrderStatus.FILLED, OrderStatus.PARTIAL, OrderStatus.REJECTED},
    OrderStatus.FILLED: {OrderStatus.CANCELLED},
    OrderStatus.PARTIAL: {OrderStatus.FILLED, OrderStatus.CANCELLED},
}


class OrderStateMachine:
    def __init__(self):
        self._status = OrderStatus.PENDING
        self._history: list[tuple[OrderStatus, datetime]] = [
            (OrderStatus.PENDING, datetime.now(timezone.utc))
        ]

    @property
    def status(self) -> OrderStatus:
        return self._status

    @property
    def history(self) -> list[tuple[OrderStatus, datetime]]:
        return self._history.copy()

    def check_expiry(self, order: ApprovedOrder) -> None:
        if order.is_expired:
            self._status = OrderStatus.TIMEOUT
            raise OrderExpiredError(f"Order {order.order_ref} expired at {order.expiry}")

    def transition(self, new_status: OrderStatus) -> None:
        valid = VALID_TRANSITIONS.get(self._status, set())
        if new_status not in valid:
            logger.warning(
                "invalid_order_transition",
                current=self._status.value,
                attempted=new_status.value,
            )
            return
        self._status = new_status
        self._history.append((new_status, datetime.now(timezone.utc)))
        logger.info("order_state_transition", new_state=new_status.value)
