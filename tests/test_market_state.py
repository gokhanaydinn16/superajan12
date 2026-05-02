from datetime import datetime, timedelta, timezone

from superajan12.market_state import MarketStateValidator
from superajan12.models import Market, OrderBookLevel, OrderBookSnapshot


def test_market_state_validator_accepts_healthy_snapshot() -> None:
    market = Market(id="m1", question="Healthy?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.49, size=300)],
        yes_asks=[OrderBookLevel(price=0.51, size=300)],
        sequence_start=101,
        sequence_end=101,
        checksum_valid=True,
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is True
    assert result.status == "healthy"
    assert result.midpoint == 0.5
    assert result.sequence_status == "validated"
    assert result.checksum_status == "validated"
    assert result.structure_status == "validated"
    assert result.freshness_status == "validated"


def test_market_state_validator_flags_crossed_book_as_invalid() -> None:
    market = Market(id="m1", question="Crossed?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.55, size=300)],
        yes_asks=[OrderBookLevel(price=0.54, size=300)],
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is False
    assert result.status == "invalid"
    assert any("crossed" in reason for reason in result.reasons)


def test_market_state_validator_marks_wide_spread_as_degraded() -> None:
    market = Market(id="m1", question="Wide spread?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.30, size=400)],
        yes_asks=[OrderBookLevel(price=0.70, size=400)],
    )

    result = MarketStateValidator(max_spread_bps=500).validate(market, book)

    assert result.ok is True
    assert result.status == "degraded"
    assert any("spread" in reason for reason in result.reasons)


def test_market_state_validator_rejects_sequence_gap() -> None:
    market = Market(id="m1", question="Gap?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.48, size=250)],
        yes_asks=[OrderBookLevel(price=0.52, size=250)],
        sequence_start=110,
        sequence_end=111,
        previous_sequence_end=100,
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is False
    assert result.sequence_status == "invalid"
    assert any("sequence gap" in reason for reason in result.reasons)


def test_market_state_validator_rejects_checksum_mismatch() -> None:
    market = Market(id="m1", question="Checksum?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.48, size=250)],
        yes_asks=[OrderBookLevel(price=0.52, size=250)],
        checksum="abc123",
        checksum_valid=False,
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is False
    assert result.checksum_status == "invalid"
    assert any("checksum" in reason for reason in result.reasons)


def test_market_state_validator_marks_synthetic_fallback_as_degraded() -> None:
    market = Market(id="m1", question="Fallback?", volume_usdc=5000, liquidity_usdc=1200)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.49, size=1)],
        yes_asks=[OrderBookLevel(price=0.51, size=1)],
        source="midpoint_spread_fallback",
        snapshot_kind="synthetic_bbo",
        is_synthetic=True,
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is True
    assert result.status == "degraded"
    assert result.is_synthetic is True
    assert any("synthetic fallback" in reason for reason in result.reasons)


def test_market_state_validator_marks_stale_snapshot_invalid() -> None:
    market = Market(id="m1", question="Stale?", volume_usdc=5000, liquidity_usdc=1200)
    stale = datetime.now(timezone.utc) - timedelta(seconds=120)
    book = OrderBookSnapshot(
        market_id="m1",
        yes_bids=[OrderBookLevel(price=0.49, size=300)],
        yes_asks=[OrderBookLevel(price=0.51, size=300)],
        captured_at=stale,
        received_at=stale,
    )

    result = MarketStateValidator().validate(market, book)

    assert result.ok is False
    assert result.freshness_status == "invalid"
    assert any("stale" in reason for reason in result.reasons)
