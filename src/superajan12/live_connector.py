from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from superajan12.execution_guard import ExecutionDecision


@dataclass(frozen=True)
class PreparedOrder:
    market_id: str
    side: str
    price: float
    size: float
    dry_run: bool
    cancel_on_disconnect: bool
    stale_after_seconds: float | None
    session_id: str | None


@dataclass(frozen=True)
class ExecutionSession:
    session_id: str
    connected: bool
    cancel_on_disconnect_supported: bool
    cancel_on_disconnect_armed: bool
    stale_data_locked: bool
    last_heartbeat_at: datetime
    disconnect_reason: str | None = None


@dataclass(frozen=True)
class DisconnectResolution:
    cancel_open_orders: bool
    activate_kill_switch: bool
    reasons: tuple[str, ...]
    session: ExecutionSession


class LiveExecutionConnector:
    """Live connector scaffold.

    This class deliberately does not send orders. It models session safety,
    stale-data locks and cancel-on-disconnect behavior before a real exchange
    adapter is introduced in a separately reviewed step.
    """

    def open_session(
        self,
        *,
        session_id: str,
        cancel_on_disconnect_supported: bool,
        cancel_on_disconnect_required: bool = True,
    ) -> ExecutionSession:
        return ExecutionSession(
            session_id=session_id,
            connected=True,
            cancel_on_disconnect_supported=cancel_on_disconnect_supported,
            cancel_on_disconnect_armed=cancel_on_disconnect_supported and cancel_on_disconnect_required,
            stale_data_locked=False,
            last_heartbeat_at=datetime.now(timezone.utc),
        )

    def mark_heartbeat(self, session: ExecutionSession, *, at: datetime | None = None) -> ExecutionSession:
        timestamp = at or datetime.now(timezone.utc)
        return ExecutionSession(
            session_id=session.session_id,
            connected=session.connected,
            cancel_on_disconnect_supported=session.cancel_on_disconnect_supported,
            cancel_on_disconnect_armed=session.cancel_on_disconnect_armed,
            stale_data_locked=False,
            last_heartbeat_at=timestamp,
            disconnect_reason=session.disconnect_reason,
        )

    def lock_stale_data(
        self,
        session: ExecutionSession,
        *,
        now: datetime | None = None,
        stale_after_seconds: float,
    ) -> ExecutionSession:
        current = now or datetime.now(timezone.utc)
        age_seconds = max((current - session.last_heartbeat_at).total_seconds(), 0.0)
        stale_locked = age_seconds > stale_after_seconds
        return ExecutionSession(
            session_id=session.session_id,
            connected=session.connected,
            cancel_on_disconnect_supported=session.cancel_on_disconnect_supported,
            cancel_on_disconnect_armed=session.cancel_on_disconnect_armed,
            stale_data_locked=stale_locked,
            last_heartbeat_at=session.last_heartbeat_at,
            disconnect_reason=session.disconnect_reason,
        )

    def handle_disconnect(
        self,
        session: ExecutionSession,
        *,
        reason: str,
        open_order_count: int,
    ) -> DisconnectResolution:
        disconnected = ExecutionSession(
            session_id=session.session_id,
            connected=False,
            cancel_on_disconnect_supported=session.cancel_on_disconnect_supported,
            cancel_on_disconnect_armed=session.cancel_on_disconnect_armed,
            stale_data_locked=True,
            last_heartbeat_at=session.last_heartbeat_at,
            disconnect_reason=reason,
        )
        cancel_open_orders = open_order_count > 0 and session.cancel_on_disconnect_armed
        activate_kill_switch = not session.cancel_on_disconnect_armed and open_order_count > 0
        reasons = [reason, "stale-data lock enabled after disconnect"]
        if cancel_open_orders:
            reasons.append("cancel-on-disconnect will clear open orders")
        if activate_kill_switch:
            reasons.append("kill-switch required because open orders cannot be canceled on disconnect")
        return DisconnectResolution(
            cancel_open_orders=cancel_open_orders,
            activate_kill_switch=activate_kill_switch,
            reasons=tuple(reasons),
            session=disconnected,
        )

    def prepare_order(
        self,
        guard_decision: ExecutionDecision,
        market_id: str,
        side: str,
        price: float,
        size: float,
        *,
        session: ExecutionSession | None = None,
        stale_after_seconds: float | None = None,
    ) -> PreparedOrder:
        if not guard_decision.allowed:
            raise RuntimeError("execution guard blocked order preparation")
        if session is not None:
            if not session.connected:
                raise RuntimeError("execution session disconnected")
            if session.stale_data_locked:
                raise RuntimeError("stale-data lock blocks order preparation")
            if guard_decision.cancel_on_disconnect_required and not session.cancel_on_disconnect_armed:
                raise RuntimeError("cancel-on-disconnect is not armed")
        if price <= 0 or price >= 1:
            raise ValueError("prediction market price must be between 0 and 1")
        if size <= 0:
            raise ValueError("order size must be positive")
        return PreparedOrder(
            market_id=market_id,
            side=side,
            price=price,
            size=size,
            dry_run=True,
            cancel_on_disconnect=bool(session and session.cancel_on_disconnect_armed),
            stale_after_seconds=stale_after_seconds,
            session_id=None if session is None else session.session_id,
        )
