from datetime import datetime, timedelta, timezone

from superajan12.approval import ManualApprovalGate
from superajan12.execution_guard import ExecutionGuard
from superajan12.live_connector import LiveExecutionConnector
from superajan12.safety import SafetyState


def _allowed_decision():
    gate = ManualApprovalGate()
    ticket = gate.approve(gate.request("live_execution", "test"), approved_by="operator")
    return ExecutionGuard(gate).can_execute(
        mode="live",
        safety_state=SafetyState(
            safe_mode=False,
            kill_switch=False,
            stale_data_lock=False,
            disconnect_lock=False,
            reasons=(),
        ),
        approval_ticket=ticket,
        secrets_ready=True,
    )


def test_live_connector_arms_cancel_on_disconnect_and_prepares_order() -> None:
    connector = LiveExecutionConnector()
    session = connector.open_session(
        session_id="sess-1",
        cancel_on_disconnect_supported=True,
        cancel_on_disconnect_required=True,
    )

    order = connector.prepare_order(
        _allowed_decision(),
        market_id="m1",
        side="YES",
        price=0.5,
        size=2.0,
        session=session,
        stale_after_seconds=15.0,
    )

    assert order.cancel_on_disconnect is True
    assert order.session_id == "sess-1"
    assert order.stale_after_seconds == 15.0


def test_live_connector_disconnect_triggers_cancel_or_kill_switch() -> None:
    connector = LiveExecutionConnector()
    armed_session = connector.open_session(
        session_id="sess-armed",
        cancel_on_disconnect_supported=True,
        cancel_on_disconnect_required=True,
    )
    unarmed_session = connector.open_session(
        session_id="sess-unarmed",
        cancel_on_disconnect_supported=False,
        cancel_on_disconnect_required=True,
    )

    armed = connector.handle_disconnect(armed_session, reason="socket dropped", open_order_count=2)
    unarmed = connector.handle_disconnect(unarmed_session, reason="socket dropped", open_order_count=2)

    assert armed.cancel_open_orders is True
    assert armed.activate_kill_switch is False
    assert armed.session.connected is False
    assert armed.session.stale_data_locked is True
    assert unarmed.cancel_open_orders is False
    assert unarmed.activate_kill_switch is True


def test_live_connector_locks_stale_data_after_heartbeat_gap() -> None:
    connector = LiveExecutionConnector()
    session = connector.open_session(
        session_id="sess-stale",
        cancel_on_disconnect_supported=True,
        cancel_on_disconnect_required=True,
    )
    old = datetime.now(timezone.utc) - timedelta(seconds=20)
    session = connector.mark_heartbeat(session, at=old)

    locked = connector.lock_stale_data(
        session,
        now=datetime.now(timezone.utc),
        stale_after_seconds=15.0,
    )

    assert locked.stale_data_locked is True
