from superajan12.agents.risk import RiskEngine
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.models import (
    Decision,
    LiquidityCheck,
    ManipulationRisk,
    Market,
    NewsReliability,
    OrderBookLevel,
    OrderBookSnapshot,
    ProbabilityEstimate,
    ReferenceReliability,
    ResolutionCheck,
    SmartWalletSignal,
    SocialSignal,
)


class _StaticDecisionAgent:
    def __init__(self, result):
        self.result = result

    def evaluate(self, *args, **kwargs):
        return self.result


class _ProbabilityAgent:
    def estimate(self, market, order_book, resolution):
        return ProbabilityEstimate(
            market_id=market.id,
            implied_probability=0.5,
            model_probability=0.55,
            edge=0.05,
            confidence=0.9,
            reasons=["strong synthetic confidence"],
        )


class _FakePolymarketClient:
    async def list_markets(self, limit: int = 25):
        return [
            Market(
                id="m1",
                question="Fallback market?",
                active=True,
                closed=False,
                volume_usdc=50_000,
                liquidity_usdc=20_000,
                raw={"clobTokenIds": ["token-1"]},
            )
        ]

    def extract_yes_token_id(self, market: Market):
        return "token-1"

    async def get_order_book_with_fallback(self, *, token_id: str, market_id: str):
        snapshot = OrderBookSnapshot(
            market_id=market_id,
            yes_bids=[OrderBookLevel(price=0.49, size=1.0)],
            yes_asks=[OrderBookLevel(price=0.51, size=1.0)],
            source="midpoint_spread_fallback",
            venue="polymarket_clob",
            token_id=token_id,
            snapshot_kind="synthetic_bbo",
            is_synthetic=True,
            depth_levels=1,
        )
        return snapshot, ["orderbook yerine midpoint/spread fallback kullanildi"]


async def test_scanner_downgrades_synthetic_market_state_to_watch() -> None:
    scanner = MarketScannerAgent(
        polymarket=_FakePolymarketClient(),
        risk_engine=RiskEngine(
            max_market_risk_usdc=25.0,
            max_daily_loss_usdc=100.0,
            min_volume_usdc=100.0,
            max_spread_bps=1_200.0,
            min_liquidity_usdc=100.0,
        ),
        resolution_agent=_StaticDecisionAgent(
            ResolutionCheck(decision=Decision.APPROVE, confidence=1.0, reasons=["resolution ok"])
        ),
        probability_agent=_ProbabilityAgent(),
        liquidity_agent=_StaticDecisionAgent(
            LiquidityCheck(
                decision=Decision.APPROVE,
                confidence=1.0,
                spread_bps=408.16,
                bid_depth_usdc=100.0,
                ask_depth_usdc=100.0,
                reasons=["liquidity ok"],
            )
        ),
        manipulation_agent=_StaticDecisionAgent(
            ManipulationRisk(decision=Decision.APPROVE, score=0.0, reasons=["manipulation ok"])
        ),
        news_agent=_StaticDecisionAgent(
            NewsReliability(decision=Decision.APPROVE, confidence=1.0, reasons=["news ok"])
        ),
        social_agent=_StaticDecisionAgent(
            SocialSignal(
                decision=Decision.APPROVE,
                confidence=1.0,
                hype_score=0.1,
                bot_risk_score=0.1,
                reasons=["social ok"],
            )
        ),
        wallet_agent=_StaticDecisionAgent(
            SmartWalletSignal(
                decision=Decision.APPROVE,
                confidence=1.0,
                wallet_score=0.1,
                flow_score=0.1,
                reasons=["wallet ok"],
            )
        ),
        reference_agent=_StaticDecisionAgent(
            ReferenceReliability(
                decision=Decision.APPROVE,
                confidence=1.0,
                max_deviation_bps=10.0,
                reasons=["reference ok"],
            )
        ),
    )

    result = await scanner.scan(limit=1)

    assert len(result.scores) == 1
    score = result.scores[0]
    assert score.decision is Decision.WATCH
    assert score.market_state_status == "degraded"
    assert score.market_state_snapshot_kind == "synthetic_bbo"
    assert score.market_state_is_synthetic is True
    assert score.market_state_sequence_status == "unavailable"
    assert score.market_state_checksum_status == "unavailable"
    assert result.ideas == []
