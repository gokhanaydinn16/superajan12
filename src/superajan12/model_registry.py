from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ModelVersion:
    name: str
    version: str
    status: str
    notes: str | None = None
    created_at: datetime = datetime.now(timezone.utc)


class ModelRegistry:
    """In-memory model version policy helper.

    Live code changes are not allowed. Model promotion must happen by explicit
    version registration and later by a manual approval gate.
    """

    allowed_statuses = {"candidate", "shadow", "approved", "retired"}

    def validate(self, version: ModelVersion) -> None:
        if not version.name.strip():
            raise ValueError("model name is required")
        if not version.version.strip():
            raise ValueError("model version is required")
        if version.status not in self.allowed_statuses:
            raise ValueError(f"invalid model status: {version.status}")

    def can_trade_live(self, version: ModelVersion) -> bool:
        return version.status == "approved"
