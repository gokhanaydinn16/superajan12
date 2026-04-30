from __future__ import annotations

from datetime import datetime, timezone

from superajan12.agents.portfolio import PaperPortfolio
from superajan12.agents.probability import ProbabilityAgent
from superajan12.agents.resolution import ResolutionAgent
from superajan12.agents.risk import RiskEngine
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.models import Decision, MarketScore, OrderBookSnapshot, PaperTradeIdea, ScanResult


class MarketScannerAgent:
    """Finds tradable Polymarket candidates and creates paper-trade ideas."""

    def __init__(
        self,
        polymarket: PolymarketClient,
        risk_engine: RiskEngine,
        resolution_agent: ResolutionAgent | None = None,
        probability_agent: ProbabilityAgent | None = None,
        paper_portfolio: PaperPortfolio | None = None,
    ) -> None:
        self.polymarket = polymarket
        self.risk_engine = risk_engine
        self.resolution_agent = resolution_agent or ResolutionAgent()
        self.probability_agent = probability_agent or ProbabilityAgent()
        self.paper_portfolio = paper_portfolio or PaperPortfolio()

    async def scan(self, limit: int = 25) -> ScanResult:
        started_at = datetime.now(timezone.utc)
        markets = await self.polymarket.list_markets(limit=limit)
        scores: list[MarketScore] = []
        ideas: list[PaperTradeIdea] = []
        paper_positions = []

        for market in markets:
            token_id = self.polymarket.extract_yes_token_id(market)
            order_book: OrderBookSnapshot | None = None
            order_book_reasons: list[str] = []

            if token_id:
                order_book = await self._load_order_book_with_fallback(token_id, market.id, order_book_reasons)
            else:
                order_book_reasons.append("YES token id bulunamadi")

            resolution = self.resolution_agent.evaluate(market)
            probability = self.probability_agent.estimate(market, order_book, resolution)
            risk = self.risk_engine.evaluate_market(market=market, order_book=order_book)

            final_decision = self._combine_decisions(
                risk_decision=risk.decision,
                resolution_decision=resolution.decision,
                probability_confidence=probability.confidence,
            )
            spread_bps = order_book.spread_bps if order_book else None
            score_value = self._score_market(
                market.volume_usdc,
                market.liquidity_usdc,
                spread_bps,
                probability.confidence,
                resolution.confidence,
            )
            reasons = [
                *order_book_reasons,
                *resolution.reasons,
                *probability.reasons,
                *risk.reasons,
            ]

            score = MarketScore(
                market_id=market.id,
                question=market.question,
                decision=final_decision,
                score=score_value,
                reasons=reasons,
                volume_usdc=market.volume_usdc,
                liquidity_usdc=market.liquidity_usdc,
                spread_bps=spread_bps,
                best_bid=order_book.best_bid if order_book else None,
                best_ask=order_book.best_ask if order_book else None,
                orderbook_source=order_book.source if order_book else None,
                implied_probability=probability.implied_probability,
                model_probability=probability.model_probability,
                edge=probability.edge,
                resolution_confidence=resolution.confidence,
                suggested_paper_risk_usdc=risk.max_risk_usdc if final_decision is Decision.APPROVE else 0.0,
            )
            scores.append(score)

            if final_decision is Decision.APPROVE:
                idea = PaperTradeIdea(
                    market_id=market.id,
                    question=market.question,
                    side="YES",
                    reference_price=order_book.mid if order_book else None,
                    risk_usdc=risk.max_risk_usdc,
                    model_probability=probability.model_probability,
                    edge=probability.edge,
                    reasons=reasons,
                )
                ideas.append(idea)
                position = self.paper_portfolio.open_from_idea(idea)
                if position is not None:
                    paper_positions.append(position)

        scores.sort(key=lambda item: item.score, reverse=True)
        return ScanResult(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            limit=limit,
            scores=scores,
            ideas=ideas,
            paper_positions=paper_positions,
        )

    async def _load_order_book_with_fallback(
        self, token_id: str, market_id: str, reasons: list[str]
    ) -> OrderBookSnapshot | None:
        try:
            return await self.polymarket.get_order_book(token_id=token_id, market_id=market_id)
        except Exception as exc:  # noqa: BLE001 - one market must not crash the whole scan
            reasons.append(f"orderbook hatasi: {exc.__class__.__name__}")

        midpoint = None
        spread = None
        try:
            midpoint = await self.polymarket.get_midpoint(token_id=token_id)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"midpoint fallback hatasi: {exc.__class__.__name__}")

        try:
            spread = await self.polymarket.get_spread(token_id=token_id)
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"spread fallback hatasi: {exc.__class__.__name__}")

        snapshot = self.polymarket.snapshot_from_mid_and_spread(
            token_id=token_id, market_id=market_id, midpoint=midpoint, spread=spread
        )
        if snapshot is not None:
            snapshot.source = "midpoint_spread_fallback"
            reasons.append("orderbook yerine midpoint/spread fallback kullanildi")
        return snapshot

    def _combine_decisions(
        self,
        risk_decision: Decision,
        resolution_decision: Decision,
        probability_confidence: float,
    ) -> Decision:
        if risk_decision is Decision.REJECT or resolution_decision is Decision.REJECT:
            return Decision.REJECT
        if resolution_decision is Decision.WATCH or probability_confidence < 0.35:
            return Decision.WATCH
        return risk_decision

    def _score_market(
        self,
        volume_usdc: float,
        liquidity_usdc: float,
        spread_bps: float | None,
        probability_confidence: float,
        resolution_confidence: float,
    ) -> float:
        spread_penalty = (spread_bps or 10_000.0) / 10_000.0
        quality_multiplier = max(0.05, (probability_confidence + resolution_confidence) / 2)
        return ((volume_usdc * 0.6 + liquidity_usdc * 0.4) / (1.0 + spread_penalty)) * quality_multiplier
