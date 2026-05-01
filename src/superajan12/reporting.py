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

    def top_scored_markets(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.sqlite_path.exists():
            return []
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT market_id, question, decision, score, implied_probability,
                           model_probability, edge, resolution_confidence, spread_bps
                    FROM market_scores
                    ORDER BY score DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []
