from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Decision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    WATCH = "watch"


class Market(BaseModel):
    id: str
    question: str
    slug: str | None = None
    category: str | None = None
    active: bool = True
    closed: bool = False
    volume_usdc: float = 0.0
    liquidity_usdc: float = 0.0
    end_date: datetime | None = None
    resolution_source: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBookSnapshot(BaseModel):
    market_id: str
    yes_bids: list[OrderBookLevel] = Field(default_factory=list)
    yes_asks: list[OrderBookLevel] = Field(default_factory=list)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_bid(self) -> float | None:
        return self.yes_bids[0].price if self.yes_bids else None

    @property
    def best_ask(self) -> float | None:
        return self.yes_asks[0].price if self.yes_asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread_bps(self) -> float | None:
        if self.best_bid is None or self.best_ask is None or self.mid in (None, 0):
            return None
        return ((self.best_ask - self.best_bid) / self.mid) * 10_000


class MarketScore(BaseModel):
    market_id: str
    question: str
    decision: Decision
    score: float
    reasons: list[str] = Field(default_factory=list)
    volume_usdc: float
    liquidity_usdc: float
    spread_bps: float | None
    suggested_paper_risk_usdc: float = 0.0


class RiskDecision(BaseModel):
    decision: Decision
    max_risk_usdc: float
    reasons: list[str] = Field(default_factory=list)


class PaperTradeIdea(BaseModel):
    market_id: str
    question: str
    side: str
    reference_price: float | None
    risk_usdc: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reasons: list[str] = Field(default_factory=list)
