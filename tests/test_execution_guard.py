from datetime import datetime, timezone

from superajan12.approval import ManualApprovalGate
from superajan12.execution_guard import ExecutionGuard
from superajan12.safety import SafetyState


def test_execution_guard_blocks_stale_disconnect_and_position_caps() -> None:
    gate = ManualApprovalGate()
    ticket = gate.approve(gate.request("live_execution", "test"), approved_by="operator")
    guard = ExecutionGuard(gate)

    decision = guard.can_execute(
        mode="live",
        safety_state=SafetyState(
            safe_mode=False,
            kill_switch=False,
            stale_data_lock=True,
            disconnect_lock=True,
            reasons=("stale data", "disconnect"),
        ),
        approval_ticket=ticket,
        secrets_ready=True,
        market_data_fresh=False,
        stale_data_age_seconds=22.0,
        stale_data_max_age_seconds=15.0,
        venue_session_connected=False,
        cancel_on_disconnect_supported=False,
        cancel_on_disconnect_required=True,
        current_open_positions=3,
        max_open_positions=3,
        requested_notional_usdc=30.0,
        max_position_notional_usdc=25.0,
        pre_trade_veto_reasons=("manual pre-trade veto",),
    )

    assert decision.allowed is False
    assert decision.stale_data_locked is True
    assert decision.hard_position_cap_hit is True
    assert "stale-data lock blocks execution" in decision.vetoes
    assert "disconnect lock blocks execution" in decision.vetoes
    assert "cancel-on-disconnect is required but unavailable" in decision.vetoes
    assert "hard open-position cap reached" in decision.vetoes
    assert "requested notional exceeds hard position cap" in decision.vetoes
    assert "manual pre-trade veto" in decision.vetoes


def test_execution_guard_allows_clean_live_context() -> None:
    gate = ManualApprovalGate()
    ticket = gate.approve(gate.request("live_execution", "test"), approved_by="operator")
    guard = ExecutionGuard(gate)

    decision = guard.can_execute(
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
        market_data_fresh=True,
        stale_data_age_seconds=2.0,
        stale_data_max_age_seconds=15.0,
        venue_session_connected=True,
        cancel_on_disconnect_supported=True,
        cancel_on_disconnect_required=True,
        current_open_positions=1,
        max_open_positions=3,
        requested_notional_usdc=10.0,
        max_position_notional_usdc=25.0,
    )

    assert decision.allowed is True
    assert decision.vetoes == ()
    assert decision.cancel_on_disconnect_required is True
