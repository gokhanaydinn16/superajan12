from __future__ import annotations

from superajan12.models import Decision, ManipulationRisk, Market, OrderBookSnapshot


class ManipulationRiskAgent:
    def evaluate(self, market: Market, order_book: OrderBookSnapshot | None) -> ManipulationRisk:
        score = 0.0
        reasons: list[str] = []
        text = f"{market.question} {market.category or ''}".lower()

        risky_terms = (
            "weather",
            "temperature",
            "sensor",
            "airport",
            "thinly traded",
            "low volume",
            "rumor",
            "unofficial",
        )
        if any(term in text for term in risky_terms):
            score += 0.25
            reasons.append("manipulasyona acik kategori/ifade bulundu")

        if market.volume_usdc < 5_000:
            score += 0.2
            reasons.append("hacim dusuk")

        if market.liquidity_usdc < 1_000:
            score += 0.2
            reasons.append("likidite dusuk")

        if order_book is None:
            score += 0.25
            reasons.append("orderbook yok")
        elif order_book.spread_bps is not None and order_book.spread_bps > 2_000:
            score += 0.2
            reasons.append("spread cok genis")

        score = max(0.0, min(1.0, score))
        if score >= 0.65:
            decision = Decision.REJECT
        elif score >= 0.35:
            decision = Decision.WATCH
        else:
            decision = Decision.APPROVE

        return ManipulationRisk(
            decision=decision,
            score=score,
            reasons=reasons or ["belirgin manipulasyon riski bulunmadi"],
        )
