from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

SHADOW_APPROVAL_MIN_OUTCOMES = 20
SHADOW_APPROVAL_MIN_WIN_RATE = 0.55
SHADOW_APPROVAL_MIN_MARKED_RATE = 0.95


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
class ShadowQualityCheck:
    ready: bool
    reasons: tuple[str, ...]


def evaluate_shadow_quality(shadow_summary: Mapping[str, object] | None) -> ShadowQualityCheck:
    if shadow_summary is None:
        return ShadowQualityCheck(ready=False, reasons=("no shadow summary available",))

    outcome_count = int(shadow_summary.get("outcome_count") or 0)
    priced_outcome_count = int(shadow_summary.get("priced_outcome_count") or 0)
    invalid_count = int(shadow_summary.get("invalid_count") or 0)
    unknown_count = int(shadow_summary.get("unknown_count") or 0)
    total_pnl = float(shadow_summary.get("total_unrealized_pnl_usdc") or 0.0)
    win_rate_raw = shadow_summary.get("win_rate")
    marked_rate_raw = shadow_summary.get("marked_rate")
    win_rate = None if win_rate_raw is None else float(win_rate_raw)
    marked_rate = None if marked_rate_raw is None else float(marked_rate_raw)

    reasons: list[str] = []
    if outcome_count < SHADOW_APPROVAL_MIN_OUTCOMES:
        reasons.append(
            f"need at least {SHADOW_APPROVAL_MIN_OUTCOMES} shadow outcomes before approval"
        )
    if priced_outcome_count < SHADOW_APPROVAL_MIN_OUTCOMES:
        reasons.append("need priced shadow outcomes before approval")
    if total_pnl <= 0:
        reasons.append("shadow PnL must stay positive before approval")
    if win_rate is None or win_rate < SHADOW_APPROVAL_MIN_WIN_RATE:
        reasons.append(
            f"shadow win rate must be at least {SHADOW_APPROVAL_MIN_WIN_RATE:.2f} before approval"
        )
    if marked_rate is None or marked_rate < SHADOW_APPROVAL_MIN_MARKED_RATE:
        reasons.append(
            f"shadow mark/fill quality must stay at or above {SHADOW_APPROVAL_MIN_MARKED_RATE:.2f}"
        )
    if invalid_count > 0:
        reasons.append("shadow results contain invalid price marks")
    if unknown_count > 0:
        reasons.append("shadow results contain unknown marks")
    if reasons:
        return ShadowQualityCheck(ready=False, reasons=tuple(reasons))
    return ShadowQualityCheck(
        ready=True,
        reasons=(
            "shadow quality gate passed "
            f"with outcomes={outcome_count}, total_pnl={total_pnl:.4f}, "
            f"win_rate={win_rate:.2f}, marked_rate={marked_rate:.2f}",
        ),
    )


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
        shadow_summary: Mapping[str, object] | None = None,
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
            reasons: list[str] = []
            if latest_score is not None and float(latest_score.get("score") or 0.0) < 0:
                reasons.append("approved model score slipped below zero; review for retirement")
            shadow_quality = evaluate_shadow_quality(shadow_summary)
            if not shadow_quality.ready:
                reasons.extend(shadow_quality.reasons)
            if reasons:
                return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=tuple(reasons))
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

        if evaluation_status == "candidate":
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
        shadow_quality = evaluate_shadow_quality(shadow_summary)
        if not shadow_quality.ready:
            reasons.extend(shadow_quality.reasons)
        if reasons:
            return ModelPromotionCheck(next_statuses=next_statuses, ready=False, reasons=tuple(reasons))
        return ModelPromotionCheck(
            next_statuses=next_statuses,
            ready=True,
            reasons=(
                f"ready for approval with sample_count={sample_count}, score={score:.4f}, win_rate={win_rate:.2f}; "
                f"{shadow_quality.reasons[0]}"
            ),
        )
