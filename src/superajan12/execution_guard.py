from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from superajan12.approval import ApprovalTicket, ManualApprovalGate
from superajan12.safety import SafetyState


@dataclass(frozen=True)
class ExecutionDecision:
    allowed: bool
    reasons: tuple[str, ...]


class ExecutionGuard:
    """Blocks any live-capable action unless all safety gates pass."""

    def __init__(self, approval_gate: ManualApprovalGate | None = None) -> None:
        self.approval_gate = approval_gate or ManualApprovalGate()

    def can_execute(
        self,
        mode: Literal["paper", "shadow", "live"],
        safety_state: SafetyState,
        approval_ticket: ApprovalTicket | None = None,
        secrets_ready: bool = False,
    ) -> ExecutionDecision:
        reasons: list[str] = []

        if mode != "live":
            return ExecutionDecision(allowed=False, reasons=("live execution disabled outside live mode",))

        if not safety_state.can_open_new_positions:
            reasons.append("safe-mode or kill-switch blocks execution")

        if not secrets_ready:
            reasons.append("required secrets are not ready")

        if approval_ticket is None or not self.approval_gate.can_execute(approval_ticket):
            reasons.append("manual approval missing")

        return ExecutionDecision(allowed=not reasons, reasons=tuple(reasons or ["all execution gates passed"]))
