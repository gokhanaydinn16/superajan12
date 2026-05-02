from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from superajan12.models import MarketScore, PaperPosition, PaperTradeIdea, ScanResult, ShadowOutcome
from superajan12.strategy import StrategyScore


class SQLiteStore:
    """Small durable store for local paper/shadow mode."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    requested_limit INTEGER NOT NULL,
                    approved_count INTEGER NOT NULL,
                    rejected_count INTEGER NOT NULL,
                    watch_count INTEGER NOT NULL,
                    idea_count INTEGER NOT NULL,
                    paper_position_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS market_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    market_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    score REAL NOT NULL,
                    volume_usdc REAL NOT NULL,
                    liquidity_usdc REAL NOT NULL,
                    spread_bps REAL,
                    best_bid REAL,
                    best_ask REAL,
                    bid_depth_usdc REAL NOT NULL DEFAULT 0,
                    ask_depth_usdc REAL NOT NULL DEFAULT 0,
                    orderbook_source TEXT,
                    market_state_status TEXT,
                    market_state_confidence REAL,
                    market_state_venue TEXT,
                    market_state_snapshot_kind TEXT,
                    market_state_sequence_status TEXT,
                    market_state_checksum_status TEXT,
                    market_state_freshness_status TEXT,
                    market_state_structure_status TEXT,
                    market_state_is_synthetic INTEGER NOT NULL DEFAULT 0,
                    implied_probability REAL,
                    model_probability REAL,
                    edge REAL,
                    resolution_confidence REAL,
                    liquidity_confidence REAL,
                    manipulation_risk_score REAL,
                    news_confidence REAL,
                    social_confidence REAL,
                    smart_wallet_confidence REAL,
                    reference_confidence REAL,
                    suggested_paper_risk_usdc REAL NOT NULL,
                    reasons_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_trade_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    market_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    side TEXT NOT NULL,
                    reference_price REAL,
                    risk_usdc REAL NOT NULL,
                    model_probability REAL,
                    edge REAL,
                    created_at TEXT NOT NULL,
                    reasons_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    market_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size_shares REAL NOT NULL,
                    risk_usdc REAL NOT NULL,
                    opened_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS shadow_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id INTEGER NOT NULL REFERENCES paper_positions(id) ON DELETE CASCADE,
                    market_id TEXT NOT NULL,
                    reference_price REAL,
                    latest_price REAL,
                    unrealized_pnl_usdc REAL,
                    status TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS strategy_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    total_pnl_usdc REAL NOT NULL,
                    win_rate REAL,
                    avg_pnl_usdc REAL,
                    score REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, version)
                );

                CREATE TABLE IF NOT EXISTS model_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version_id INTEGER NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    reason TEXT,
                    changed_by TEXT NOT NULL DEFAULT 'system',
                    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS readiness_checklists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    label TEXT NOT NULL,
                    passed INTEGER NOT NULL DEFAULT 0,
                    detail TEXT,
                    updated_by TEXT NOT NULL DEFAULT 'system',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(scope, item_key)
                );

                CREATE TABLE IF NOT EXISTS operator_acknowledgements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    note TEXT,
                    acknowledged_by TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS execution_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    connected INTEGER NOT NULL DEFAULT 1,
                    cancel_on_disconnect_supported INTEGER NOT NULL DEFAULT 0,
                    cancel_on_disconnect_armed INTEGER NOT NULL DEFAULT 0,
                    stale_data_locked INTEGER NOT NULL DEFAULT 0,
                    disconnect_reason TEXT,
                    open_order_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS execution_veto_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    veto_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            for table, column, ddl in (
                ("scans", "paper_position_count", "INTEGER NOT NULL DEFAULT 0"),
                ("market_scores", "bid_depth_usdc", "REAL NOT NULL DEFAULT 0"),
                ("market_scores", "ask_depth_usdc", "REAL NOT NULL DEFAULT 0"),
                ("market_scores", "orderbook_source", "TEXT"),
                ("market_scores", "market_state_status", "TEXT"),
                ("market_scores", "market_state_confidence", "REAL"),
                ("market_scores", "market_state_venue", "TEXT"),
                ("market_scores", "market_state_snapshot_kind", "TEXT"),
                ("market_scores", "market_state_sequence_status", "TEXT"),
                ("market_scores", "market_state_checksum_status", "TEXT"),
                ("market_scores", "market_state_freshness_status", "TEXT"),
                ("market_scores", "market_state_structure_status", "TEXT"),
                ("market_scores", "market_state_is_synthetic", "INTEGER NOT NULL DEFAULT 0"),
                ("market_scores", "implied_probability", "REAL"),
                ("market_scores", "model_probability", "REAL"),
                ("market_scores", "edge", "REAL"),
                ("market_scores", "resolution_confidence", "REAL"),
                ("market_scores", "liquidity_confidence", "REAL"),
                ("market_scores", "manipulation_risk_score", "REAL"),
                ("market_scores", "news_confidence", "REAL"),
                ("market_scores", "social_confidence", "REAL"),
                ("market_scores", "smart_wallet_confidence", "REAL"),
                ("market_scores", "reference_confidence", "REAL"),
                ("paper_trade_ideas", "model_probability", "REAL"),
                ("paper_trade_ideas", "edge", "REAL"),
                ("execution_sessions", "open_order_count", "INTEGER NOT NULL DEFAULT 0"),
            ):
                self._ensure_column(conn, table, column, ddl)

    def save_scan(self, result: ScanResult) -> int:
        approved = sum(1 for item in result.scores if item.decision.value == "approve")
        rejected = sum(1 for item in result.scores if item.decision.value == "reject")
        watch = sum(1 for item in result.scores if item.decision.value == "watch")

        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scans (
                    started_at, finished_at, requested_limit,
                    approved_count, rejected_count, watch_count, idea_count, paper_position_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.started_at.isoformat(),
                    result.finished_at.isoformat(),
                    result.limit,
                    approved,
                    rejected,
                    watch,
                    len(result.ideas),
                    len(result.paper_positions),
                ),
            )
            scan_id = int(cursor.lastrowid)
            self._insert_scores(conn, scan_id, result.scores)
            self._insert_ideas(conn, scan_id, result.ideas)
            self._insert_positions(conn, scan_id, result.paper_positions)
            return scan_id

    def latest_scan_summary(self) -> dict[str, int | float | str] | None:
        with self.connect() as conn:
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

    def list_open_positions(self) -> list[dict[str, object]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, market_id, question, side, entry_price, size_shares, risk_usdc, opened_at, status
                FROM paper_positions
                WHERE status = 'open'
                ORDER BY id ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def save_shadow_outcome(self, position_id: int, outcome: ShadowOutcome) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO shadow_outcomes (
                    position_id, market_id, reference_price, latest_price,
                    unrealized_pnl_usdc, status, reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position_id,
                    outcome.market_id,
                    outcome.reference_price,
                    outcome.latest_price,
                    outcome.unrealized_pnl_usdc,
                    outcome.status,
                    json.dumps(outcome.reasons, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def shadow_summary(self) -> dict[str, object]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT COUNT(*) AS outcome_count,
                       COALESCE(SUM(unrealized_pnl_usdc), 0) AS total_unrealized_pnl_usdc,
                       AVG(unrealized_pnl_usdc) AS avg_unrealized_pnl_usdc,
                       SUM(CASE WHEN unrealized_pnl_usdc > 0 THEN 1 ELSE 0 END) AS wins
                FROM shadow_outcomes
                WHERE unrealized_pnl_usdc IS NOT NULL
                """
            ).fetchone()
            result = dict(row)
            count = int(result.get("outcome_count") or 0)
            wins = int(result.get("wins") or 0)
            result["win_rate"] = None if count == 0 else wins / count
            return result

    def save_strategy_score(self, score: StrategyScore) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategy_scores (
                    strategy_name, sample_count, total_pnl_usdc, win_rate, avg_pnl_usdc, score
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    score.strategy_name,
                    score.sample_count,
                    score.total_pnl_usdc,
                    score.win_rate,
                    score.avg_pnl_usdc,
                    score.score,
                ),
            )
            return int(cursor.lastrowid)

    def list_strategy_scores(self, limit: int = 10) -> list[dict[str, object]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, strategy_name, sample_count, total_pnl_usdc, win_rate,
                       avg_pnl_usdc, score, created_at
                FROM strategy_scores
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_model_version(
        self,
        name: str,
        version: str,
        status: str,
        notes: str | None = None,
        change_reason: str | None = None,
        changed_by: str = "system",
    ) -> int:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id, status FROM model_versions WHERE name = ? AND version = ?",
                (name, version),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO model_versions (name, version, status, notes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name, version) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (name, version, status, notes),
            )
            row = conn.execute(
                "SELECT id FROM model_versions WHERE name = ? AND version = ?",
                (name, version),
            ).fetchone()
            if row is None:
                raise RuntimeError("model version save failed")
            model_version_id = int(row["id"])
            previous_status = None if existing is None else str(existing["status"])
            if existing is None or previous_status != status:
                conn.execute(
                    """
                    INSERT INTO model_status_history (
                        model_version_id, name, version, from_status, to_status, reason, changed_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_version_id,
                        name,
                        version,
                        previous_status,
                        status,
                        change_reason or notes or f"status set to {status}",
                        changed_by,
                    ),
                )
            return model_version_id

    def list_model_versions(self, limit: int = 20) -> list[dict[str, object]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, name, version, status, notes, created_at
                FROM model_versions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_model_status_history(self, limit: int = 50) -> list[dict[str, object]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, model_version_id, name, version, from_status, to_status,
                       reason, changed_by, changed_at
                FROM model_status_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def set_readiness_item(
        self,
        *,
        scope: str,
        item_key: str,
        label: str,
        passed: bool,
        detail: str | None = None,
        updated_by: str = "system",
    ) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO readiness_checklists (scope, item_key, label, passed, detail, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, item_key) DO UPDATE SET
                    label = excluded.label,
                    passed = excluded.passed,
                    detail = excluded.detail,
                    updated_by = excluded.updated_by,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (scope, item_key, label, 1 if passed else 0, detail, updated_by),
            )
            row = conn.execute(
                "SELECT id FROM readiness_checklists WHERE scope = ? AND item_key = ?",
                (scope, item_key),
            ).fetchone()
            if row is None:
                raise RuntimeError("readiness checklist save failed")
            return int(row[0])

    def list_readiness_items(self, scope: str) -> list[dict[str, object]]:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, scope, item_key, label, passed, detail, updated_by, updated_at
                FROM readiness_checklists
                WHERE scope = ?
                ORDER BY item_key ASC
                """,
                (scope,),
            ).fetchall()
            items = [dict(row) for row in rows]
            for item in items:
                item["passed"] = bool(item.get("passed"))
            return items

    def record_operator_acknowledgement(
        self,
        *,
        scope: str,
        acknowledged: bool,
        note: str | None,
        acknowledged_by: str,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO operator_acknowledgements (scope, acknowledged, note, acknowledged_by)
                VALUES (?, ?, ?, ?)
                """,
                (scope, 1 if acknowledged else 0, note, acknowledged_by),
            )
            return int(cursor.lastrowid)

    def latest_operator_acknowledgement(self, scope: str) -> dict[str, object] | None:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, scope, acknowledged, note, acknowledged_by, created_at
                FROM operator_acknowledgements
                WHERE scope = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (scope,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["acknowledged"] = bool(result.get("acknowledged"))
            return result

    def save_execution_session(
        self,
        *,
        session_id: str,
        connected: bool,
        cancel_on_disconnect_supported: bool,
        cancel_on_disconnect_armed: bool,
        stale_data_locked: bool,
        disconnect_reason: str | None,
        open_order_count: int,
    ) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO execution_sessions (
                    session_id, connected, cancel_on_disconnect_supported,
                    cancel_on_disconnect_armed, stale_data_locked, disconnect_reason,
                    open_order_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    connected = excluded.connected,
                    cancel_on_disconnect_supported = excluded.cancel_on_disconnect_supported,
                    cancel_on_disconnect_armed = excluded.cancel_on_disconnect_armed,
                    stale_data_locked = excluded.stale_data_locked,
                    disconnect_reason = excluded.disconnect_reason,
                    open_order_count = excluded.open_order_count,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    1 if connected else 0,
                    1 if cancel_on_disconnect_supported else 0,
                    1 if cancel_on_disconnect_armed else 0,
                    1 if stale_data_locked else 0,
                    disconnect_reason,
                    open_order_count,
                ),
            )
            row = conn.execute(
                "SELECT id FROM execution_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("execution session save failed")
            return int(row[0])

    def latest_execution_session(self) -> dict[str, object] | None:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, session_id, connected, cancel_on_disconnect_supported,
                       cancel_on_disconnect_armed, stale_data_locked, disconnect_reason,
                       open_order_count, updated_at
                FROM execution_sessions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            for key in (
                "connected",
                "cancel_on_disconnect_supported",
                "cancel_on_disconnect_armed",
                "stale_data_locked",
            ):
                result[key] = bool(result.get(key))
            return result

    def record_execution_veto(self, *, scope: str, vetoes: tuple[str, ...] | list[str]) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO execution_veto_events (scope, veto_json)
                VALUES (?, ?)
                """,
                (scope, json.dumps(list(vetoes), ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    def latest_execution_veto(self, scope: str) -> dict[str, object] | None:
        with self.connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, scope, veto_json, created_at
                FROM execution_veto_events
                WHERE scope = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (scope,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["vetoes"] = json.loads(str(result.pop("veto_json") or "[]"))
            return result

    def _insert_scores(self, conn: sqlite3.Connection, scan_id: int, scores: Iterable[MarketScore]) -> None:
        conn.executemany(
            """
            INSERT INTO market_scores (
                scan_id, market_id, question, decision, score, volume_usdc,
                liquidity_usdc, spread_bps, best_bid, best_ask, bid_depth_usdc,
                ask_depth_usdc, orderbook_source, market_state_status, market_state_confidence,
                market_state_venue, market_state_snapshot_kind, market_state_sequence_status,
                market_state_checksum_status, market_state_freshness_status,
                market_state_structure_status, market_state_is_synthetic, implied_probability,
                model_probability, edge, resolution_confidence, liquidity_confidence,
                manipulation_risk_score, news_confidence, social_confidence,
                smart_wallet_confidence, reference_confidence, suggested_paper_risk_usdc,
                reasons_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    score.market_id,
                    score.question,
                    score.decision.value,
                    score.score,
                    score.volume_usdc,
                    score.liquidity_usdc,
                    score.spread_bps,
                    score.best_bid,
                    score.best_ask,
                    score.bid_depth_usdc,
                    score.ask_depth_usdc,
                    score.orderbook_source,
                    score.market_state_status,
                    score.market_state_confidence,
                    score.market_state_venue,
                    score.market_state_snapshot_kind,
                    score.market_state_sequence_status,
                    score.market_state_checksum_status,
                    score.market_state_freshness_status,
                    score.market_state_structure_status,
                    1 if score.market_state_is_synthetic else 0,
                    score.implied_probability,
                    score.model_probability,
                    score.edge,
                    score.resolution_confidence,
                    score.liquidity_confidence,
                    score.manipulation_risk_score,
                    score.news_confidence,
                    score.social_confidence,
                    score.smart_wallet_confidence,
                    score.reference_confidence,
                    score.suggested_paper_risk_usdc,
                    json.dumps(score.reasons, ensure_ascii=False),
                )
                for score in scores
            ],
        )

    def _insert_ideas(self, conn: sqlite3.Connection, scan_id: int, ideas: Iterable[PaperTradeIdea]) -> None:
        conn.executemany(
            """
            INSERT INTO paper_trade_ideas (
                scan_id, market_id, question, side, reference_price,
                risk_usdc, model_probability, edge, created_at, reasons_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    idea.market_id,
                    idea.question,
                    idea.side,
                    idea.reference_price,
                    idea.risk_usdc,
                    idea.model_probability,
                    idea.edge,
                    idea.created_at.isoformat(),
                    json.dumps(idea.reasons, ensure_ascii=False),
                )
                for idea in ideas
            ],
        )

    def _insert_positions(self, conn: sqlite3.Connection, scan_id: int, positions: Iterable[PaperPosition]) -> None:
        conn.executemany(
            """
            INSERT INTO paper_positions (
                scan_id, market_id, question, side, entry_price,
                size_shares, risk_usdc, opened_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    position.market_id,
                    position.question,
                    position.side,
                    position.entry_price,
                    position.size_shares,
                    position.risk_usdc,
                    position.opened_at.isoformat(),
                    position.status,
                )
                for position in positions
            ],
        )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
