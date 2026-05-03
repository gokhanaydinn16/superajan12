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


@dataclass(frozen=True)
class LiveModelReadiness:
    ready: bool
    blockers: tuple[str, ...]


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
        current_status: str | None = None,
    ) -> ModelPromotionCheck:
        evaluation_status = current_status or version.status
        next_statuses = self.allowed_transitions(evaluation_status)

        if current_status is not None:
            if version.status == evaluation_status:
                return ModelPromotionCheck(
                    next_statuses=next_statuses,
                    ready=False,
                    reasons=(f"model is already in {evaluation_status} status",),
                )
            if version.status not in next_statuses:
                return ModelPromotionCheck(
                    next_statuses=next_statuses,
                    ready=False,
                    reasons=(f"cannot transition from {evaluation_status} to {version.status}",),
                )
            if version.status == "retired":
                return ModelPromotionCheck(
                    next_statuses=next_statuses,
                    ready=True,
                    reasons=(f"ready to retire model from {evaluation_status}",),
                )

        if evaluation_status == "retired":
            return ModelPromotionCheck(
                next_statuses=next_statuses,
                ready=False,
                reasons=("retired models cannot be promoted",),
            )

        if evaluation_status == "approved":
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
        total_pnl = float(latest_score.get("total_pnl_usdc") or 0.0)
        avg_pnl = float(latest_score.get("avg_pnl_usdc") or 0.0)
        win_rate_raw = latest_score.get("win_rate")
        win_rate = None if win_rate_raw is None else float(win_rate_raw)

        if evaluation_status == "candidate":
            reasons: list[str] = []
            if sample_count < 20:
                reasons.append("need at least 20 scored outcomes for shadow promotion")
            if score <= 0:
                reasons.append("strategy score must be positive for shadow promotion")
            if total_pnl <= 0:
                reasons.append("total pnl must be positive for shadow promotion")
            if reasons:
                return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=tuple(reasons))
            return ModelPromotionCheck(
                next_statuses=next_statuses,
                ready=True,
                reasons=(
                    f"ready for shadow promotion with sample_count={sample_count}, score={score:.4f}, total_pnl={total_pnl:.4f}",
                ),
            )

        reasons = []
        if sample_count < 50:
            reasons.append("need at least 50 scored outcomes for approval")
        if score <= 0:
            reasons.append("strategy score must stay positive for approval")
        if total_pnl <= 0:
            reasons.append("total pnl must stay positive for approval")
        if avg_pnl <= 0:
            reasons.append("average pnl must stay positive for approval")
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

    def evaluate_live_readiness(
        self,
        version: ModelVersion,
        latest_score: Mapping[str, object] | None = None,
        readiness_items: list[Mapping[str, object]] | None = None,
    ) -> LiveModelReadiness:
        blockers: list[str] = []

        if version.status != "approved":
            blockers.append("model must be approved before live activation")

        if latest_score is None:
            blockers.append("latest strategy score is missing")
        else:
            sample_count = int(latest_score.get("sample_count") or 0)
            score = float(latest_score.get("score") or 0.0)
            total_pnl = float(latest_score.get("total_pnl_usdc") or 0.0)
            win_rate_raw = latest_score.get("win_rate")
            win_rate = None if win_rate_raw is None else float(win_rate_raw)
            if sample_count < 100:
                blockers.append("live activation requires at least 100 scored outcomes")
            if score <= 0:
                blockers.append("live activation requires a positive strategy score")
            if total_pnl <= 0:
                blockers.append("live activation requires positive total pnl")
            if win_rate is None or win_rate < 0.55:
                blockers.append("live activation requires win rate of at least 0.55")

        for item in readiness_items or []:
            if not bool(item.get("passed")):
                label = str(item.get("label") or item.get("item_key") or "readiness item")
                blockers.append(f"checklist blocker: {label}")

        return LiveModelReadiness(ready=not blockers, blockers=tuple(blockers))
