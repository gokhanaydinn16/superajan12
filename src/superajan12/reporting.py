from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class Reporter:
    """Read-only reporting helpers for local paper/shadow mode."""

    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path

    def latest_summary(self) -> dict[str, Any] | None:
        if not self.sqlite_path.exists():
            return None
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, started_at, finished_at, requested_limit, approved_count,
                           rejected_count, watch_count, idea_count, paper_position_count
                    FROM scans
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
                return None if row is None else dict(row)
        except sqlite3.OperationalError:
            return None

    def aggregate_summary(self) -> dict[str, Any]:
        if not self.sqlite_path.exists():
            return {
                "scan_count": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "watch_count": 0,
                "idea_count": 0,
                "paper_position_count": 0,
            }
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS scan_count,
                           COALESCE(SUM(approved_count), 0) AS approved_count,
                           COALESCE(SUM(rejected_count), 0) AS rejected_count,
                           COALESCE(SUM(watch_count), 0) AS watch_count,
                           COALESCE(SUM(idea_count), 0) AS idea_count,
                           COALESCE(SUM(paper_position_count), 0) AS paper_position_count
                    FROM scans
                    """
                ).fetchone()
                return dict(row)
        except sqlite3.OperationalError:
            return {
                "scan_count": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "watch_count": 0,
                "idea_count": 0,
                "paper_position_count": 0,
            }

    def top_scored_markets(self, limit: int = 10, latest_scan_only: bool = True) -> list[dict[str, Any]]:
        if not self.sqlite_path.exists():
            return []
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                if latest_scan_only:
                    rows = conn.execute(
                        """
                        SELECT market_id, question, category, decision, score, volume_usdc, liquidity_usdc,
                               spread_bps, best_bid, best_ask, bid_depth_usdc, ask_depth_usdc,
                               orderbook_source, market_state_status, market_state_confidence,
                               market_state_venue, market_state_snapshot_kind,
                               market_state_sequence_status, market_state_checksum_status,
                               market_state_freshness_status, market_state_structure_status,
                               market_state_is_synthetic, implied_probability, model_probability, edge,
                               resolution_confidence, liquidity_confidence, manipulation_risk_score,
                               news_confidence, social_confidence, smart_wallet_confidence,
                               reference_confidence, suggested_paper_risk_usdc
                        FROM market_scores
                        WHERE scan_id = (
                            SELECT id
                            FROM scans
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        ORDER BY score DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT market_id, question, category, decision, score, volume_usdc, liquidity_usdc,
                               spread_bps, best_bid, best_ask, bid_depth_usdc, ask_depth_usdc,
                               orderbook_source, market_state_status, market_state_confidence,
                               market_state_venue, market_state_snapshot_kind,
                               market_state_sequence_status, market_state_checksum_status,
                               market_state_freshness_status, market_state_structure_status,
                               market_state_is_synthetic, implied_probability, model_probability, edge,
                               resolution_confidence, liquidity_confidence, manipulation_risk_score,
                               news_confidence, social_confidence, smart_wallet_confidence,
                               reference_confidence, suggested_paper_risk_usdc
                        FROM market_scores
                        ORDER BY score DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                items = [dict(row) for row in rows]
                for item in items:
                    item["market_state_is_synthetic"] = bool(item.get("market_state_is_synthetic"))
                return items
        except sqlite3.OperationalError:
            return []

    def category_summary(self, latest_scan_only: bool = True) -> list[dict[str, Any]]:
        if not self.sqlite_path.exists():
            return []
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                params: tuple[object, ...] = ()
                query = """
                    SELECT COALESCE(category, 'uncategorized') AS category,
                           COUNT(*) AS market_count,
                           COALESCE(AVG(score), 0) AS avg_score,
                           COALESCE(AVG(edge), 0) AS avg_edge,
                           COALESCE(SUM(volume_usdc), 0) AS total_volume_usdc,
                           COALESCE(SUM(liquidity_usdc), 0) AS total_liquidity_usdc,
                           SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END) AS approve_count,
                           SUM(CASE WHEN decision = 'watch' THEN 1 ELSE 0 END) AS watch_count,
                           SUM(CASE WHEN decision = 'reject' THEN 1 ELSE 0 END) AS reject_count
                    FROM market_scores
                """
                if latest_scan_only:
                    query += """
                        WHERE scan_id = (
                            SELECT id FROM scans ORDER BY id DESC LIMIT 1
                        )
                    """
                query += """
                    GROUP BY COALESCE(category, 'uncategorized')
                    ORDER BY avg_score DESC, total_volume_usdc DESC
                """
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []

    def shadow_category_summary(self) -> list[dict[str, Any]]:
        if not self.sqlite_path.exists():
            return []
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT COALESCE(p.category, 'uncategorized') AS category,
                           COUNT(*) AS outcome_count,
                           COALESCE(SUM(s.unrealized_pnl_usdc), 0) AS total_unrealized_pnl_usdc,
                           AVG(s.unrealized_pnl_usdc) AS avg_unrealized_pnl_usdc,
                           SUM(CASE WHEN s.unrealized_pnl_usdc > 0 THEN 1 ELSE 0 END) AS wins
                    FROM shadow_outcomes s
                    JOIN paper_positions p ON p.id = s.position_id
                    WHERE s.unrealized_pnl_usdc IS NOT NULL
                    GROUP BY COALESCE(p.category, 'uncategorized')
                    ORDER BY total_unrealized_pnl_usdc DESC, outcome_count DESC
                    """
                ).fetchall()
                items = [dict(row) for row in rows]
                for item in items:
                    count = int(item.get("outcome_count") or 0)
                    wins = int(item.get("wins") or 0)
                    item["win_rate"] = None if count == 0 else wins / count
                return items
        except sqlite3.OperationalError:
            return []
