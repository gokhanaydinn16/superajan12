from superajan12.agents.cross_market import CrossMarketAgent
from superajan12.agents.liquidity import LiquidityAgent
from superajan12.agents.manipulation import ManipulationRiskAgent
from superajan12.agents.news import NewsReliabilityAgent
from superajan12.models import Decision, Market, OrderBookLevel, OrderBookSnapshot


def test_liquidity_agent_approves_clean_book() -> None:
    market = Market(id="m1", question="Test?", liquidity_usdc=5_000)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.49, size=200)],
        yes_asks=[OrderBookLevel(price=0.51, size=200)],
    )

    result = LiquidityAgent().evaluate(market, book)

    assert result.decision == Decision.APPROVE
    assert result.confidence > 0.6


def test_manipulation_agent_flags_weather_low_liquidity() -> None:
    market = Market(id="m1", question="Will airport weather sensor report 30C?", volume_usdc=100, liquidity_usdc=50)

    result = ManipulationRiskAgent().evaluate(market, None)

    assert result.decision in {Decision.WATCH, Decision.REJECT}
    assert result.score >= 0.35


def test_news_agent_rewards_official_source() -> None:
    market = Market(
        id="m1",
        question="Will official result be certified?",
        resolution_source="official",
        raw={"description": "Will resolve according to official final result."},
    )

    result = NewsReliabilityAgent().evaluate(market)

    assert result.decision == Decision.APPROVE
    assert result.confidence >= 0.75


def test_cross_market_agent_finds_similar_title() -> None:
    market = Market(id="pm1", question="Will Bitcoin hit 100k in 2026?")
    external = [{"ticker": "KXBTC100K", "title": "Will Bitcoin hit 100k in 2026?", "yes_bid": 52}]

    matches = CrossMarketAgent().find_matches(market, external)

    assert len(matches) == 1
    assert matches[0].external_id == "KXBTC100K"
    assert matches[0].yes_price == 0.52
