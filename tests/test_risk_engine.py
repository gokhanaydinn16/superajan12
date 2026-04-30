from superajan12.agents.risk import RiskEngine
from superajan12.models import Decision, Market, OrderBookLevel, OrderBookSnapshot


def make_engine() -> RiskEngine:
    return RiskEngine(
        max_market_risk_usdc=10,
        max_daily_loss_usdc=25,
        min_volume_usdc=1000,
        max_spread_bps=1200,
        min_liquidity_usdc=250,
    )


def test_risk_engine_rejects_low_volume_market() -> None:
    market = Market(id="1", question="Test?", volume_usdc=10, liquidity_usdc=500)
    book = OrderBookSnapshot(
        market_id="1",
        yes_bids=[OrderBookLevel(price=0.49, size=100)],
        yes_asks=[OrderBookLevel(price=0.51, size=100)],
    )

    decision = make_engine().evaluate_market(market, book)

    assert decision.decision == Decision.REJECT
    assert any("hacim dusuk" in reason for reason in decision.reasons)


def test_risk_engine_approves_clean_market() -> None:
    market = Market(id="1", question="Test?", volume_usdc=5000, liquidity_usdc=1000)
    book = OrderBookSnapshot(
        market_id="1",
        yes_bids=[OrderBookLevel(price=0.49, size=100)],
        yes_asks=[OrderBookLevel(price=0.51, size=100)],
    )

    decision = make_engine().evaluate_market(market, book)

    assert decision.decision == Decision.APPROVE
    assert decision.max_risk_usdc == 10
