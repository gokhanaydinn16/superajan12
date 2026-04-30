from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ApprovalTicket:
    action: str
    reason: str
    created_at: datetime
    approved: bool = False
    approved_by: str | None = None


class ManualApprovalGate:
    """Manual approval gate for any future live-capable action."""

    def request(self, action: str, reason: str) -> ApprovalTicket:
        return ApprovalTicket(action=action, reason=reason, created_at=datetime.now(timezone.utc))

    def approve(self, ticket: ApprovalTicket, approved_by: str) -> ApprovalTicket:
        return ApprovalTicket(
            action=ticket.action,
            reason=ticket.reason,
            created_at=ticket.created_at,
            approved=True,
            approved_by=approved_by,
        )

    def can_execute(self, ticket: ApprovalTicket) -> bool:
        return ticket.approved and bool(ticket.approved_by)
