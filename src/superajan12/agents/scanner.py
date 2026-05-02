from __future__ import annotations

from datetime import datetime, timezone

from superajan12.agents.liquidity import LiquidityAgent
from superajan12.agents.manipulation import ManipulationRiskAgent
from superajan12.agents.news import NewsReliabilityAgent
from superajan12.agents.portfolio import PaperPortfolio
from superajan12.agents.probability import ProbabilityAgent
from superajan12.agents.reference import ReferenceCheck
from superajan12.agents.reference_reliability import ReferenceReliabilityAgent
from superajan12.agents.resolution import ResolutionAgent
from superajan12.agents.risk import RiskEngine
from superajan12.agents.social import SocialSignalAgent
from superajan12.agents.wallet import SmartWalletAgent
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.market_state import MarketStateValidation, MarketStateValidator
from superajan12.models import Decision, MarketScore, OrderBookSnapshot, PaperTradeIdea, ScanResult


class MarketScannerAgent:
    """Find tradable Polymarket candidates and create paper-trade ideas."""

    def __init__(
        self,
        polymarket: PolymarketClient,
        risk_engine: RiskEngine,
        resolution_agent: ResolutionAgent | None = None,
        probability_agent: ProbabilityAgent | None = None,
        liquidity_agent: LiquidityAgent | None = None,
        manipulation_agent: ManipulationRiskAgent | None = None,
        news_agent: NewsReliabilityAgent | None = None,
        social_agent: SocialSignalAgent | None = None,
        wallet_agent: SmartWalletAgent | None = None,
        reference_agent: ReferenceReliabilityAgent | None = None,
        reference_checks: list[ReferenceCheck] | None = None,
        paper_portfolio: PaperPortfolio | None = None,
        market_state_validator: MarketStateValidator | None = None,
    ) -> None:
        self.polymarket = polymarket
        self.risk_engine = risk_engine
        self.resolution_agent = resolution_agent or ResolutionAgent()
        self.probability_agent = probability_agent or ProbabilityAgent()
        self.liquidity_agent = liquidity_agent or LiquidityAgent()
        self.manipulation_agent = manipulation_agent or ManipulationRiskAgent()
        self.news_agent = news_agent or NewsReliabilityAgent()
        self.social_agent = social_agent or SocialSignalAgent()
        self.wallet_agent = wallet_agent or SmartWalletAgent()
        self.reference_agent = reference_agent or ReferenceReliabilityAgent()
        self.reference_checks = reference_checks or []
        self.paper_portfolio = paper_portfolio or PaperPortfolio()
        self.market_state_validator = market_state_validator or MarketStateValidator()

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
                order_book, load_reasons = await self.polymarket.get_order_book_with_fallback(
                    token_id=token_id,
                    market_id=market.id,
                )
                order_book_reasons.extend(load_reasons)
            else:
                order_book_reasons.append("YES token id bulunamadi")

            market_state = self.market_state_validator.validate(market, order_book)
            analysis_book = order_book if market_state.ok else None

            resolution = self.resolution_agent.evaluate(market)
            liquidity = self.liquidity_agent.evaluate(market, analysis_book)
            manipulation = self.manipulation_agent.evaluate(market, analysis_book)
            news = self.news_agent.evaluate(market)
            social = self.social_agent.evaluate(market)
            wallet = self.wallet_agent.evaluate(market)
            reference = self.reference_agent.evaluate(market, self.reference_checks)
            probability = self.probability_agent.estimate(market, analysis_book, resolution)
            risk = self.risk_engine.evaluate_market(
                market=market,
                order_book=analysis_book,
                reference_gate_ok=reference.decision is not Decision.REJECT,
                reference_gate_reasons=reference.reasons,
            )

            final_decision = self._combine_decisions(
                market_state_decision=self._market_state_decision(market_state),
                risk_decision=risk.decision,
                resolution_decision=resolution.decision,
                liquidity_decision=liquidity.decision,
                manipulation_decision=manipulation.decision,
                news_decision=news.decision,
                social_decision=social.decision,
                wallet_decision=wallet.decision,
                reference_decision=reference.decision,
                probability_confidence=probability.confidence,
            )
            spread_bps = analysis_book.spread_bps if analysis_book else None
            score_value = self._score_market(
                volume_usdc=market.volume_usdc,
                liquidity_usdc=market.liquidity_usdc,
                spread_bps=spread_bps,
                probability_confidence=probability.confidence,
                resolution_confidence=resolution.confidence,
                liquidity_confidence=liquidity.confidence,
                manipulation_safety=1.0 - manipulation.score,
                news_confidence=news.confidence,
                social_confidence=social.confidence,
                wallet_confidence=wallet.confidence,
                reference_confidence=reference.confidence,
                market_state_confidence=market_state.confidence,
            )
            reasons = [
                *order_book_reasons,
                *market_state.reasons,
                *resolution.reasons,
                *liquidity.reasons,
                *manipulation.reasons,
                *news.reasons,
                *social.reasons,
                *wallet.reasons,
                *reference.reasons,
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
                spread_bps=market_state.spread_bps,
                best_bid=analysis_book.best_bid if analysis_book else None,
                best_ask=analysis_book.best_ask if analysis_book else None,
                bid_depth_usdc=market_state.bid_depth_usdc,
                ask_depth_usdc=market_state.ask_depth_usdc,
                orderbook_source=market_state.orderbook_source,
                market_state_status=market_state.status,
                market_state_confidence=market_state.confidence,
                market_state_venue=market_state.venue,
                market_state_snapshot_kind=market_state.snapshot_kind,
                market_state_sequence_status=market_state.sequence_status,
                market_state_checksum_status=market_state.checksum_status,
                market_state_freshness_status=market_state.freshness_status,
                market_state_structure_status=market_state.structure_status,
                market_state_is_synthetic=market_state.is_synthetic,
                implied_probability=probability.implied_probability,
                model_probability=probability.model_probability,
                edge=probability.edge,
                resolution_confidence=resolution.confidence,
                liquidity_confidence=liquidity.confidence,
                manipulation_risk_score=manipulation.score,
                news_confidence=news.confidence,
                social_confidence=social.confidence,
                smart_wallet_confidence=wallet.confidence,
                reference_confidence=reference.confidence,
                suggested_paper_risk_usdc=risk.max_risk_usdc if final_decision is Decision.APPROVE else 0.0,
            )
            scores.append(score)

            if final_decision is Decision.APPROVE:
                idea = PaperTradeIdea(
                    market_id=market.id,
                    question=market.question,
                    side="YES",
                    reference_price=analysis_book.mid if analysis_book else None,
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

    def _market_state_decision(self, validation: MarketStateValidation) -> Decision:
        if not validation.ok:
            return Decision.REJECT
        if validation.status == "degraded":
            return Decision.WATCH
        return Decision.APPROVE

    def _combine_decisions(
        self,
        market_state_decision: Decision,
        risk_decision: Decision,
        resolution_decision: Decision,
        liquidity_decision: Decision,
        manipulation_decision: Decision,
        news_decision: Decision,
        social_decision: Decision,
        wallet_decision: Decision,
        reference_decision: Decision,
        probability_confidence: float,
    ) -> Decision:
        hard_decisions = (
            market_state_decision,
            risk_decision,
            resolution_decision,
            liquidity_decision,
            manipulation_decision,
            news_decision,
            social_decision,
            wallet_decision,
            reference_decision,
        )
        if Decision.REJECT in hard_decisions:
            return Decision.REJECT
        if Decision.WATCH in hard_decisions or probability_confidence < 0.35:
            return Decision.WATCH
        return risk_decision

    def _score_market(
        self,
        *,
        volume_usdc: float,
        liquidity_usdc: float,
        spread_bps: float | None,
        probability_confidence: float,
        resolution_confidence: float,
        liquidity_confidence: float,
        manipulation_safety: float,
        news_confidence: float,
        social_confidence: float,
        wallet_confidence: float,
        reference_confidence: float,
        market_state_confidence: float,
    ) -> float:
        spread_penalty = (spread_bps or 10_000.0) / 10_000.0
        quality_multiplier = max(
            0.05,
            (
                probability_confidence
                + resolution_confidence
                + liquidity_confidence
                + manipulation_safety
                + news_confidence
                + social_confidence
                + wallet_confidence
                + reference_confidence
                + market_state_confidence
            )
            / 9,
        )
        return ((volume_usdc * 0.6 + liquidity_usdc * 0.4) / (1.0 + spread_penalty)) * quality_multiplier
