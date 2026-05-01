from datetime import datetime, timezone

from superajan12.models import Decision, MarketScore, ScanResult
from superajan12.reporting import Reporter
from superajan12.storage import SQLiteStore


def _build_scan_result(market_id: str, score: float) -> ScanResult:
    return ScanResult(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        limit=1,
        scores=[
            MarketScore(
                market_id=market_id,
                question=f"Question for {market_id}?",
                decision=Decision.APPROVE,
                score=score,
                volume_usdc=5000,
                liquidity_usdc=1000,
                spread_bps=80,
                best_bid=0.49,
                best_ask=0.51,
                bid_depth_usdc=100,
                ask_depth_usdc=100,
                orderbook_source="book",
                implied_probability=0.5,
                model_probability=0.6,
                edge=0.1,
                resolution_confidence=0.9,
                suggested_paper_risk_usdc=10,
                reasons=["ok"],
            )
        ],
        ideas=[],
        paper_positions=[],
    )


def test_top_scored_markets_defaults_to_latest_scan(tmp_path) -> None:
    path = tmp_path / "superajan12.sqlite3"
    store = SQLiteStore(path)
    reporter = Reporter(path)

    store.save_scan(_build_scan_result("older-market", 999.0))
    store.save_scan(_build_scan_result("latest-market", 100.0))

    latest_only = reporter.top_scored_markets(limit=1)
    all_scans = reporter.top_scored_markets(limit=1, latest_scan_only=False)

    assert latest_only[0]["market_id"] == "latest-market"
    assert latest_only[0]["liquidity_usdc"] == 1000
    assert latest_only[0]["orderbook_source"] == "book"
    assert latest_only[0]["suggested_paper_risk_usdc"] == 10
    assert all_scans[0]["market_id"] == "older-market"
