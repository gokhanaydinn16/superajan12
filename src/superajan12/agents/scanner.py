from __future__ import annotations

from superajan12.agents.risk import RiskEngine
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.models import Decision, MarketScore, OrderBookSnapshot, PaperTradeIdea


class MarketScannerAgent:
    """Finds tradable Polymarket candidates and creates paper-trade ideas."""

    def __init__(self, polymarket: PolymarketClient, risk_engine: RiskEngine) -> None:
        self.polymarket = polymarket
        self.risk_engine = risk_engine

    async def scan(self, limit: int = 25) -> tuple[list[MarketScore], list[PaperTradeIdea]]:
        markets = await self.polymarket.list_markets(limit=limit)
        scores: list[MarketScore] = []
        ideas: list[PaperTradeIdea] = []

        for market in markets:
            token_id = self.polymarket.extract_yes_token_id(market)
            order_book: OrderBookSnapshot | None = None
            order_book_reasons: list[str] = []

            if token_id:
                try:
                    order_book = await self.polymarket.get_order_book(token_id=token_id, market_id=market.id)
                except Exception as exc:  # noqa: BLE001 - scanner must not crash on one market
                    order_book_reasons.append(f"orderbook hatasi: {exc.__class__.__name__}")
            else:
                order_book_reasons.append("YES token id bulunamadi")

            risk = self.risk_engine.evaluate_market(market=market, order_book=order_book)
            spread_bps = order_book.spread_bps if order_book else None
            score_value = self._score_market(market.volume_usdc, market.liquidity_usdc, spread_bps)
            reasons = [*order_book_reasons, *risk.reasons]

            score = MarketScore(
                market_id=market.id,
                question=market.question,
                decision=risk.decision,
                score=score_value,
                reasons=reasons,
                volume_usdc=market.volume_usdc,
                liquidity_usdc=market.liquidity_usdc,
                spread_bps=spread_bps,
                suggested_paper_risk_usdc=risk.max_risk_usdc,
            )
            scores.append(score)

            if risk.decision is Decision.APPROVE:
                ideas.append(
                    PaperTradeIdea(
                        market_id=market.id,
                        question=market.question,
                        side="YES",
                        reference_price=order_book.mid if order_book else None,
                        risk_usdc=risk.max_risk_usdc,
                        reasons=reasons,
                    )
                )

        scores.sort(key=lambda item: item.score, reverse=True)
        return scores, ideas

    def _score_market(self, volume_usdc: float, liquidity_usdc: float, spread_bps: float | None) -> float:
        spread_penalty = (spread_bps or 10_000.0) / 10_000.0
        return (volume_usdc * 0.6 + liquidity_usdc * 0.4) / (1.0 + spread_penalty)
