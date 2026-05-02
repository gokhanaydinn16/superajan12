from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from superajan12.approval import ApprovalTicket, ManualApprovalGate
from superajan12.safety import SafetyState


@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    reasons: tuple[str, ...]
    vetoes: tuple[str, ...]
    stale_data_locked: bool
    hard_position_cap_hit: bool
    cancel_on_disconnect_required: bool


class ExecutionGuard:
    """Block any live-capable action unless all safety gates pass."""

    def __init__(self, approval_gate: ManualApprovalGate | None = None) -> None:
        self.approval_gate = approval_gate or ManualApprovalGate()

    def can_execute(
        self,
        mode: Literal["paper", "shadow", "live"],
        safety_state: SafetyState,
        approval_ticket: ApprovalTicket | None = None,
        secrets_ready: bool = False,
        *,
        market_data_fresh: bool = True,
        stale_data_age_seconds: float | None = None,
        stale_data_max_age_seconds: float | None = None,
        venue_session_connected: bool = True,
        cancel_on_disconnect_supported: bool = True,
        cancel_on_disconnect_required: bool = True,
        current_open_positions: int = 0,
        max_open_positions: int | None = None,
        requested_notional_usdc: float | None = None,
        max_position_notional_usdc: float | None = None,
        pre_trade_veto_reasons: tuple[str, ...] | list[str] | None = None,
    ) -> ExecutionDecision:
        vetoes: list[str] = []
        notes: list[str] = []

        if mode != "live":
            vetoes.append("live execution disabled outside live mode")

        if safety_state.kill_switch:
            vetoes.append("kill-switch blocks execution")
        if safety_state.safe_mode:
            vetoes.append("safe-mode blocks execution")
        if safety_state.stale_data_lock:
            vetoes.append("stale-data lock blocks execution")
        if safety_state.disconnect_lock:
            vetoes.append("disconnect lock blocks execution")

        if not secrets_ready:
            vetoes.append("required secrets are not ready")

        if approval_ticket is None or not self.approval_gate.can_execute(approval_ticket):
            vetoes.append("manual approval missing")

        if not venue_session_connected:
            vetoes.append("venue session disconnected")

        if cancel_on_disconnect_required and not cancel_on_disconnect_supported:
            vetoes.append("cancel-on-disconnect is required but unavailable")

        stale_data_locked = False
        if not market_data_fresh:
            stale_data_locked = True
            if stale_data_age_seconds is not None and stale_data_max_age_seconds is not None:
                vetoes.append(
                    f"market data stale: {stale_data_age_seconds:.1f}s > {stale_data_max_age_seconds:.1f}s"
                )
            else:
                vetoes.append("market data stale")

        hard_position_cap_hit = False
        if max_open_positions is not None and current_open_positions >= max_open_positions:
            hard_position_cap_hit = True
            vetoes.append("hard open-position cap reached")

        if (
            requested_notional_usdc is not None
            and max_position_notional_usdc is not None
            and requested_notional_usdc > max_position_notional_usdc
        ):
            hard_position_cap_hit = True
            vetoes.append("requested notional exceeds hard position cap")

        if pre_trade_veto_reasons:
            vetoes.extend(str(reason) for reason in pre_trade_veto_reasons if str(reason).strip())

        if cancel_on_disconnect_required and cancel_on_disconnect_supported:
            notes.append("cancel-on-disconnect armed")
        if market_data_fresh:
            notes.append("market data fresh")
        if not hard_position_cap_hit:
            notes.append("position caps within limits")

        reasons = tuple(vetoes if vetoes else notes or ["all execution gates passed"])
        return ExecutionDecision(
            allowed=not vetoes,
            reasons=reasons,
            vetoes=tuple(vetoes),
            stale_data_locked=stale_data_locked,
            hard_position_cap_hit=hard_position_cap_hit,
            cancel_on_disconnect_required=cancel_on_disconnect_required,
        )
