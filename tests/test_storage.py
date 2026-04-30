from datetime import datetime, timezone

from superajan12.models import Decision, MarketScore, PaperTradeIdea, ScanResult
from superajan12.storage import SQLiteStore


def test_sqlite_store_saves_scan(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "superajan12.sqlite3")
    result = ScanResult(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        limit=1,
        scores=[
            MarketScore(
                market_id="m1",
                question="Test market?",
                decision=Decision.APPROVE,
                score=123.0,
                volume_usdc=5000,
                liquidity_usdc=1000,
                spread_bps=100,
                best_bid=0.49,
                best_ask=0.51,
                orderbook_source="book",
                suggested_paper_risk_usdc=10,
                reasons=["risk kontrolleri gecti"],
            )
        ],
        ideas=[
            PaperTradeIdea(
                market_id="m1",
                question="Test market?",
                side="YES",
                reference_price=0.5,
                risk_usdc=10,
                reasons=["risk kontrolleri gecti"],
            )
        ],
    )

    scan_id = store.save_scan(result)

    assert scan_id == 1
    with store.connect() as conn:
        scan_count = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        score_count = conn.execute("SELECT COUNT(*) FROM market_scores").fetchone()[0]
        idea_count = conn.execute("SELECT COUNT(*) FROM paper_trade_ideas").fetchone()[0]

    assert scan_count == 1
    assert score_count == 1
    assert idea_count == 1
