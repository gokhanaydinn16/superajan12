from superajan12.agents.reference_reliability import ReferenceReliabilityAgent
from superajan12.agents.social import SocialSignalAgent
from superajan12.agents.wallet import SmartWalletAgent
from superajan12.models import Decision, Market, PaperPosition
from superajan12.shadow import ShadowEvaluator


class GoodReference:
    symbol = "BTC"
    ok = True
    max_deviation_bps = 10.0


class BadReference:
    symbol = "BTC"
    ok = False
    max_deviation_bps = 200.0


def test_social_agent_watches_hype_language() -> None:
    market = Market(id="m1", question="Will the viral meme coin pump after rumor?")

    result = SocialSignalAgent().evaluate(market)

    assert result.decision in {Decision.WATCH, Decision.REJECT}
    assert result.hype_score > 0


def test_wallet_agent_stays_conservative_without_data() -> None:
    market = Market(id="m1", question="Will Bitcoin hit 100k?")

    result = SmartWalletAgent().evaluate(market)

    assert result.decision in {Decision.WATCH, Decision.APPROVE}
    assert result.wallet_score == 0.0


def test_reference_reliability_rejects_bad_crypto_sources() -> None:
    market = Market(id="m1", question="Will BTC close above 100k?")

    result = ReferenceReliabilityAgent().evaluate(market, [BadReference()])

    assert result.decision == Decision.REJECT
    assert result.confidence < 0.5


def test_reference_reliability_approves_good_crypto_sources() -> None:
    market = Market(id="m1", question="Will BTC close above 100k?")

    result = ReferenceReliabilityAgent().evaluate(market, [GoodReference()])

    assert result.decision == Decision.APPROVE
    assert result.confidence > 0.5


def test_shadow_evaluator_marks_yes_position() -> None:
    position = PaperPosition(
        market_id="m1",
        question="Test?",
        side="YES",
        entry_price=0.40,
        size_shares=25,
        risk_usdc=10,
    )

    outcome = ShadowEvaluator().evaluate_position(position, latest_price=0.50)

    assert outcome.status == "marked"
    assert round(outcome.unrealized_pnl_usdc or 0, 2) == 2.50
