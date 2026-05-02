from datetime import datetime, timezone

from superajan12.models import Decision, MarketScore, ScanResult
from superajan12.reporting import Reporter
from superajan12.storage import SQLiteStore


def test_storage_and_reporting_preserve_market_state_fields(tmp_path) -> None:
    sqlite_path = tmp_path / "market-state.sqlite3"
    store = SQLiteStore(sqlite_path)

    score = MarketScore(
        market_id="m1",
        question="Persist market state?",
        decision=Decision.WATCH,
        score=42.0,
        reasons=["synthetic fallback snapshot in use"],
        volume_usdc=10_000,
        liquidity_usdc=2_000,
        spread_bps=400.0,
        best_bid=0.49,
        best_ask=0.51,
        bid_depth_usdc=120.0,
        ask_depth_usdc=130.0,
        orderbook_source="midpoint_spread_fallback",
        market_state_status="degraded",
        market_state_confidence=0.64,
        market_state_venue="polymarket_clob",
        market_state_snapshot_kind="synthetic_bbo",
        market_state_sequence_status="unavailable",
        market_state_checksum_status="unavailable",
        market_state_freshness_status="validated",
        market_state_structure_status="validated",
        market_state_is_synthetic=True,
        implied_probability=0.5,
        model_probability=0.55,
        edge=0.05,
        resolution_confidence=0.9,
        liquidity_confidence=0.8,
        manipulation_risk_score=0.1,
        news_confidence=0.7,
        social_confidence=0.6,
        smart_wallet_confidence=0.5,
        reference_confidence=0.9,
        suggested_paper_risk_usdc=0.0,
    )
    result = ScanResult(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        limit=1,
        scores=[score],
        ideas=[],
        paper_positions=[],
    )

    store.save_scan(result)
    rows = Reporter(sqlite_path).top_scored_markets(limit=1)

    assert len(rows) == 1
    row = rows[0]
    assert row["market_state_status"] == "degraded"
    assert row["market_state_snapshot_kind"] == "synthetic_bbo"
    assert row["market_state_sequence_status"] == "unavailable"
    assert row["market_state_checksum_status"] == "unavailable"
    assert row["market_state_is_synthetic"] is True
