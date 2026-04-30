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
    source: str = "book"
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

    @property
    def bid_depth_usdc(self) -> float:
        return sum(level.price * level.size for level in self.yes_bids)

    @property
    def ask_depth_usdc(self) -> float:
        return sum(level.price * level.size for level in self.yes_asks)


class ResolutionCheck(BaseModel):
    decision: Decision
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    source: str | None = None


class LiquidityCheck(BaseModel):
    decision: Decision
    confidence: float
    spread_bps: float | None
    bid_depth_usdc: float
    ask_depth_usdc: float
    reasons: list[str] = Field(default_factory=list)


class ManipulationRisk(BaseModel):
    decision: Decision
    score: float
    reasons: list[str] = Field(default_factory=list)


class NewsReliability(BaseModel):
    decision: Decision
    confidence: float
    reasons: list[str] = Field(default_factory=list)


class SocialSignal(BaseModel):
    decision: Decision
    confidence: float
    hype_score: float
    bot_risk_score: float
    reasons: list[str] = Field(default_factory=list)


class SmartWalletSignal(BaseModel):
    decision: Decision
    confidence: float
    wallet_score: float
    flow_score: float
    reasons: list[str] = Field(default_factory=list)


class ReferenceReliability(BaseModel):
    decision: Decision
    confidence: float
    max_deviation_bps: float | None = None
    reasons: list[str] = Field(default_factory=list)


class ProbabilityEstimate(BaseModel):
    market_id: str
    implied_probability: float | None
    model_probability: float | None
    edge: float | None
    confidence: float
    reasons: list[str] = Field(default_factory=list)


class MarketScore(BaseModel):
    market_id: str
    question: str
    decision: Decision
    score: float
    reasons: list[str] = Field(default_factory=list)
    volume_usdc: float
    liquidity_usdc: float
    spread_bps: float | None
    best_bid: float | None = None
    best_ask: float | None = None
    bid_depth_usdc: float = 0.0
    ask_depth_usdc: float = 0.0
    orderbook_source: str | None = None
    implied_probability: float | None = None
    model_probability: float | None = None
    edge: float | None = None
    resolution_confidence: float | None = None
    liquidity_confidence: float | None = None
    manipulation_risk_score: float | None = None
    news_confidence: float | None = None
    social_confidence: float | None = None
    smart_wallet_confidence: float | None = None
    reference_confidence: float | None = None
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
    model_probability: float | None = None
    edge: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reasons: list[str] = Field(default_factory=list)


class PaperPosition(BaseModel):
    market_id: str
    question: str
    side: str
    entry_price: float
    size_shares: float
    risk_usdc: float
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "open"

    @property
    def notional_usdc(self) -> float:
        return self.entry_price * self.size_shares


class CrossMarketMatch(BaseModel):
    source: str
    external_id: str
    external_title: str
    similarity: float
    yes_price: float | None = None
    no_price: float | None = None
    reasons: list[str] = Field(default_factory=list)


class ShadowOutcome(BaseModel):
    market_id: str
    reference_price: float | None
    latest_price: float | None
    unrealized_pnl_usdc: float | None
    status: str
    reasons: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    started_at: datetime
    finished_at: datetime
    limit: int
    scores: list[MarketScore]
    ideas: list[PaperTradeIdea]
    paper_positions: list[PaperPosition] = Field(default_factory=list)
