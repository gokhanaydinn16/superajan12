from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping


@dataclass(frozen=True)
class ModelVersion:
    name: str
    version: str
    status: str
    notes: str | None = None
    created_at: datetime = datetime.now(timezone.utc)


@dataclass(frozen=True)
class ModelPromotionCheck:
    next_statuses: tuple[str, ...]
    ready: bool
    reasons: tuple[str, ...]


class ModelRegistry:
    """In-memory model version policy helper.

    Live code changes are not allowed. Model promotion must happen by explicit
    version registration and later by a manual approval gate.
    """

    allowed_statuses = {"candidate", "shadow", "approved", "retired"}
    transition_map = {
        "candidate": ("shadow", "retired"),
        "shadow": ("approved", "retired"),
        "approved": ("retired",),
        "retired": (),
    }

    def validate(self, version: ModelVersion) -> None:
        if not version.name.strip():
            raise ValueError("model name is required")
        if not version.version.strip():
            raise ValueError("model version is required")
        if version.status not in self.allowed_statuses:
            raise ValueError(f"invalid model status: {version.status}")

    def can_trade_live(self, version: ModelVersion) -> bool:
        return version.status == "approved"

    def allowed_transitions(self, status: str) -> tuple[str, ...]:
        return self.transition_map.get(status, ())

    def evaluate_promotion(
        self,
        version: ModelVersion,
        latest_score: Mapping[str, object] | None = None,
    ) -> ModelPromotionCheck:
        next_statuses = self.allowed_transitions(version.status)
        if version.status == "retired":
            return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=("retired models cannot be promoted",))

        if version.status == "approved":
            if latest_score is not None and float(latest_score.get("score") or 0.0) < 0:
                return ModelPromotionCheck(
                    next_statuses=next_statuses,
                    ready=False,
                    reasons=("approved model score slipped below zero; review for retirement",),
                )
            return ModelPromotionCheck(
                next_statuses=next_statuses,
                ready=False,
                reasons=("approved model is already live-eligible",),
            )

        if latest_score is None:
            return ModelPromotionCheck(
                next_statuses=next_statuses,
                ready=False,
                reasons=("no strategy score recorded yet",),
            )

        sample_count = int(latest_score.get("sample_count") or 0)
        score = float(latest_score.get("score") or 0.0)
        win_rate_raw = latest_score.get("win_rate")
        win_rate = None if win_rate_raw is None else float(win_rate_raw)

        if version.status == "candidate":
            reasons: list[str] = []
            if sample_count < 20:
                reasons.append("need at least 20 scored outcomes for shadow promotion")
            if score <= 0:
                reasons.append("strategy score must be positive for shadow promotion")
            if reasons:
                return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=tuple(reasons))
            return ModelPromotionCheck(
                next_statuses=next_statuses,
                ready=True,
                reasons=(f"ready for shadow promotion with sample_count={sample_count} and score={score:.4f}",),
            )

        reasons = []
        if sample_count < 50:
            reasons.append("need at least 50 scored outcomes for approval")
        if score <= 0:
            reasons.append("strategy score must stay positive for approval")
        if win_rate is None or win_rate < 0.5:
            reasons.append("win rate must be at least 0.50 for approval")
        if reasons:
            return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=tuple(reasons))
        return ModelPromotionCheck(
            next_statuses=next_statuses,
            ready=True,
            reasons=(
                f"ready for approval with sample_count={sample_count}, score={score:.4f}, win_rate={win_rate:.2f}",
            ),
        )
