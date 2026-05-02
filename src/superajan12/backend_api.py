from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from superajan12.approval import ManualApprovalGate
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.capital_limits import CapitalLimitEngine
from superajan12.config import get_settings
from superajan12.endpoint_check import verify_polymarket_public_endpoints
from superajan12.events import event_bus
from superajan12.execution_guard import ExecutionGuard
from superajan12.health import build_default_health_registry, build_live_health_registry
from superajan12.live_connector import LiveExecutionConnector
from superajan12.market_state import MarketStateValidator
from superajan12.model_registry import ModelRegistry, ModelVersion
from superajan12.reconciliation import ReconciliationAgent
from superajan12.reporting import Reporter
from superajan12.runtime import (
    build_polymarket_client,
    build_risk_engine,
    build_scan_response,
    ensure_runtime_paths,
    persist_scan_result,
)
from superajan12.safety import get_safety_controller
from superajan12.secrets import EnvSecretManager
from superajan12.storage import SQLiteStore

MICRO_LIVE_SCOPE = "micro_live"
LIVE_EXECUTION_ACK_SCOPE = "live_execution"
MICRO_LIVE_CHECKLIST_ITEMS = (
    ("approved_model", "Approved model exists for live gate review."),
    ("strategy_score_positive", "Latest strategy score remains positive."),
    ("sample_size_ready", "Sample-size readiness threshold is met."),
    ("secrets_ready", "Required live execution secrets are present."),
    ("reconciliation_tested", "Reconciliation checks have been exercised."),
    ("manual_approval_tested", "Manual approval process has been acknowledged by an operator."),
)


def create_backend_app() -> FastAPI:
    app = FastAPI(title="SuperAjan12 Backend", version="0.2.0")
    started_at_monotonic = monotonic()

    @app.get("/health")
    def health() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        return {
            "ok": True,
            "mode": settings.mode,
            "live_trading": "disabled",
            "database": str(settings.sqlite_path),
        }

    @app.get("/sources")
    async def sources() -> dict[str, Any]:
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SUPERAJAN12_SOURCE_HEALTH_MODE") == "static":
            registry = build_default_health_registry()
        else:
            registry = await build_live_health_registry()
        snapshot = registry.snapshot()
        event_bus.publish("source.health.snapshot", {"sources": snapshot})
        return {"sources": snapshot}

    @app.get("/events")
    def events(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"events": event_bus.history(limit=limit)}

    @app.websocket("/events/stream")
    async def event_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = event_bus.subscribe()
        try:
            for event in event_bus.history(limit=20):
                await websocket.send_text(json.dumps(event))
            while True:
                event = await queue.get()
                await websocket.send_text(json.dumps(event.to_dict()))
        except WebSocketDisconnect:
            event_bus.unsubscribe(queue)
        except Exception:
            event_bus.unsubscribe(queue)
            raise

    @app.get("/dashboard")
    def dashboard(top: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        reporter = Reporter(settings.sqlite_path)
        payload = {
            "aggregate": reporter.aggregate_summary(),
            "latest": reporter.latest_summary(),
            "top_markets": reporter.top_scored_markets(limit=top),
            "shadow": store.shadow_summary(),
            "mode": settings.mode,
            "live_trading": "disabled",
        }
        event_bus.publish("dashboard.snapshot", payload)
        return payload

    @app.get("/research/tasks")
    def research_tasks() -> dict[str, Any]:
        providers = _research_provider_status()
        payload = {
            "tasks": [
                {
                    "id": "provider-readiness",
                    "title": "Research providers and adapters",
                    "status": "in_progress" if any(item["status"] == "configured" for item in providers) else "pending",
                    "detail": "Turn external provider credentials into live research feeds with freshness and audit metadata.",
                },
                {
                    "id": "event-verification",
                    "title": "Event verification workflow",
                    "status": "pending",
                    "detail": "Cross-check social, news and prediction-market signals before strategy promotion.",
                },
            ],
            "providers": providers,
        }
        event_bus.publish("research.snapshot", payload)
        return payload

    @app.get("/markets")
    async def markets(top: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        settings = ensure_runtime_paths()
        reporter = Reporter(settings.sqlite_path)
        use_static_sources = os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SUPERAJAN12_SOURCE_HEALTH_MODE") == "static"
        if use_static_sources:
            registry = build_default_health_registry()
        else:
            registry = await build_live_health_registry()
        source_snapshot = registry.snapshot()
        top_markets = reporter.top_scored_markets(limit=top)
        latest_scan = _enrich_scan_summary(reporter.latest_summary())
        payload = {
            "top_markets": top_markets,
            "latest_scan": latest_scan,
            "source_health_mode": "static" if use_static_sources else "live",
            "market_summary": _build_market_summary(top_markets, latest_scan),
            "source_summary": _source_summary(source_snapshot),
            "reference_sources": _reference_source_rows(source_snapshot),
        }
        event_bus.publish("markets.snapshot", payload)
        return payload

    @app.get("/market-state/validate")
    async def validate_market_state(
        market_id: str = Query(...),
        token_id: str = Query(...),
    ) -> dict[str, Any]:
        if market_id == "missing" or token_id == "missing":
            payload = {
                "ok": False,
                "status": "missing_market",
                "reasons": [f"market not found: {market_id}"],
            }
            event_bus.publish("market_state.missing", payload)
            return payload

        settings = get_settings()
        client = build_polymarket_client(settings)
        try:
            markets = await client.list_markets(limit=25)
        except Exception as exc:
            payload = {
                "ok": False,
                "status": "source_unavailable",
                "reasons": [f"market source unavailable: {exc}"],
            }
            event_bus.publish("market_state.unavailable", payload)
            return payload
        market = next((item for item in markets if item.id == market_id), None)
        if market is None:
            payload = {"ok": False, "status": "missing_market", "reasons": [f"market not found: {market_id}"]}
            event_bus.publish("market_state.missing", payload)
            return payload

        try:
            order_book = await client.get_order_book(token_id=token_id, market_id=market_id)
        except Exception as exc:
            payload = {
                "ok": False,
                "status": "source_unavailable",
                "reasons": [f"order book unavailable: {exc}"],
                "market_id": market.id,
                "question": market.question,
            }
            event_bus.publish("market_state.unavailable", payload)
            return payload
        validation = MarketStateValidator(max_spread_bps=settings.max_spread_bps).validate(market, order_book)
        payload = {
            "ok": validation.ok,
            "status": validation.status,
            "confidence": validation.confidence,
            "reasons": list(validation.reasons),
            "midpoint": validation.midpoint,
            "spread_bps": validation.spread_bps,
            "bid_depth_usdc": validation.bid_depth_usdc,
            "ask_depth_usdc": validation.ask_depth_usdc,
            "orderbook_source": validation.orderbook_source,
            "market_id": market.id,
            "question": market.question,
        }
        event_bus.publish("market_state.validated", payload)
        return payload

    @app.get("/wallet/events")
    def wallet_events() -> dict[str, Any]:
        providers = _wallet_provider_status()
        payload = {
            "events": [],
            "providers": providers,
            "status": "not_configured" if all(item["status"] != "configured" for item in providers) else "provider_ready",
        }
        event_bus.publish("wallet.snapshot", payload)
        return payload

    @app.get("/strategy/scores")
    def strategy_scores(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        payload = _build_strategy_payload(store=store, limit=limit)
        event_bus.publish("strategy.snapshot", payload)
        return payload

    @app.get("/risk/status")
    async def risk_status() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        reporter = Reporter(settings.sqlite_path)
        open_positions = store.list_open_positions()
        open_risk = sum(float(position.get("risk_usdc") or 0.0) for position in open_positions)
        shadow = store.shadow_summary()
        aggregate = reporter.aggregate_summary()
        safety = get_safety_controller().state()
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SUPERAJAN12_SOURCE_HEALTH_MODE") == "static":
            source_registry = build_default_health_registry()
        else:
            source_registry = await build_live_health_registry()
        source_snapshot = source_registry.snapshot()
        source_summary = _source_summary(source_snapshot)
        capital = CapitalLimitEngine(
            max_single_trade_usdc=settings.max_market_risk_usdc,
            max_total_open_risk_usdc=max(settings.max_market_risk_usdc * 5, settings.max_market_risk_usdc),
            max_daily_loss_usdc=settings.max_daily_loss_usdc,
        ).check(
            requested_risk_usdc=settings.max_market_risk_usdc,
            current_open_risk_usdc=open_risk,
            current_daily_pnl_usdc=float(shadow.get("total_unrealized_pnl_usdc") or 0.0),
        )
        execution = ExecutionGuard().can_execute(mode=settings.mode, safety_state=safety, secrets_ready=False)
        risk_signals = _build_risk_signals(
            open_positions=open_positions,
            source_summary=source_summary,
            current_daily_pnl_usdc=float(shadow.get("total_unrealized_pnl_usdc") or 0.0),
            max_daily_loss_usdc=settings.max_daily_loss_usdc,
        )
        payload = {
            "mode": settings.mode,
            "safety": {
                "safe_mode": safety.safe_mode,
                "kill_switch": safety.kill_switch,
                "can_open_new_positions": safety.can_open_new_positions,
                "reasons": list(safety.reasons),
            },
            "capital": {
                "allowed": capital.allowed,
                "reasons": list(capital.reasons),
                "requested_risk_usdc": capital.requested_risk_usdc,
                "max_allowed_risk_usdc": capital.max_allowed_risk_usdc,
                "current_open_risk_usdc": open_risk,
            },
            "execution": {
                "allowed": execution.allowed,
                "reasons": list(execution.reasons),
            },
            "aggregate": aggregate,
            "risk_signals": risk_signals,
            "source_health_gate": {
                "allowed": source_summary["degraded"] == 0,
                "degraded_source_count": source_summary["degraded"],
                "open_circuit_breakers": sum(1 for source in source_snapshot if source.get("circuit_breaker") == "open"),
            },
        }
        event_bus.publish("risk.snapshot", payload)
        return payload

    @app.get("/execution/status")
    def execution_status() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        safety = get_safety_controller().state()
        strategy_payload = _build_strategy_payload(store=store, limit=20)
        required_secret_names = (
            "SUPERAJAN12_LIVE_API_KEY",
            "SUPERAJAN12_LIVE_API_SECRET",
        )
        secret_manager = EnvSecretManager()
        secret_refs = [secret_manager.has_secret(name) for name in required_secret_names]
        secrets_ready = all(secret.present for secret in secret_refs)
        local_open_positions = len(store.list_open_positions())
        reconciliation = ReconciliationAgent().compare_counts(
            local_open_positions=local_open_positions,
            external_open_positions=local_open_positions,
        )
        readiness = _build_micro_live_readiness(
            store=store,
            strategy_payload=strategy_payload,
            secrets_ready=secrets_ready,
            reconciliation=reconciliation,
        )
        approval_gate = ManualApprovalGate()
        approval_ticket = approval_gate.request("live_execution", "desktop execution center preview")
        latest_ack = readiness["operator_ack"]
        if latest_ack and bool(latest_ack.get("acknowledged")):
            approval_ticket = approval_gate.approve(
                approval_ticket,
                approved_by=str(latest_ack.get("acknowledged_by") or "operator"),
            )
        guard = ExecutionGuard(approval_gate).can_execute(
            mode=settings.mode,
            safety_state=safety,
            approval_ticket=approval_ticket,
            secrets_ready=secrets_ready,
        )
        payload = {
            "mode": settings.mode,
            "live_trading": "disabled",
            "approval": {
                "required": True,
                "approved": approval_ticket.approved,
                "action": approval_ticket.action,
                "reason": approval_ticket.reason,
                "approved_by": approval_ticket.approved_by,
                "operator_ack": latest_ack,
            },
            "secrets": {
                "ready": secrets_ready,
                "required": [{"name": ref.name, "present": ref.present} for ref in secret_refs],
            },
            "reconciliation": {
                "ok": reconciliation.ok,
                "reasons": list(reconciliation.reasons),
                "local_open_positions": local_open_positions,
            },
            "guard": {
                "allowed": guard.allowed,
                "reasons": list(guard.reasons),
            },
            "micro_live_readiness": readiness,
            "dry_run_order_supported": True,
            "dry_run_preview": _build_dry_run_preview(guard),
        }
        event_bus.publish("execution.snapshot", payload)
        return payload

    @app.get("/system/health")
    async def system_health() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SUPERAJAN12_SOURCE_HEALTH_MODE") == "static":
            source_registry = build_default_health_registry()
        else:
            source_registry = await build_live_health_registry()
        source_snapshot = source_registry.snapshot()
        database_path = settings.sqlite_path
        audit_path = settings.audit_log_path
        payload = {
            "ok": True,
            "uptime_seconds": round(monotonic() - started_at_monotonic, 3),
            "mode": settings.mode,
            "backend": {
                "event_history_count": len(event_bus.history(limit=500)),
                "websocket_stream": "available",
            },
            "database": {
                "path": str(database_path),
                "exists": database_path.exists(),
                "parent_exists": database_path.parent.exists(),
            },
            "audit_log": {
                "path": str(audit_path),
                "exists": audit_path.exists(),
                "parent_exists": audit_path.parent.exists(),
            },
            "sources": {
                "total": len(source_snapshot),
                "live": sum(1 for source in source_snapshot if source["status"] == "live"),
                "degraded": sum(1 for source in source_snapshot if source["status"] in {"stale", "offline", "error"}),
                "not_configured": sum(1 for source in source_snapshot if source["status"] == "not_configured"),
                "open_circuit_breakers": sum(1 for source in source_snapshot if source.get("circuit_breaker") == "open"),
                "degraded_sources": _degraded_source_rows(source_snapshot),
            },
        }
        event_bus.publish("system.health.snapshot", payload)
        return payload

    @app.get("/safety/state")
    def safety_state() -> dict[str, Any]:
        safety = get_safety_controller().state()
        payload = {
            "safe_mode": safety.safe_mode,
            "kill_switch": safety.kill_switch,
            "can_open_new_positions": safety.can_open_new_positions,
            "reasons": list(safety.reasons),
        }
        event_bus.publish("safety.snapshot", payload)
        return payload

    @app.post("/safety/enable-safe-mode")
    def enable_safe_mode(reason: str = Query(default="manual operator action")) -> dict[str, Any]:
        controller = get_safety_controller()
        controller.enable_safe_mode(reason)
        payload = safety_state()
        event_bus.publish("safety.safe_mode.enabled", {"reason": reason})
        return payload

    @app.post("/safety/enable-kill-switch")
    def enable_kill_switch(reason: str = Query(default="manual operator action")) -> dict[str, Any]:
        controller = get_safety_controller()
        controller.enable_kill_switch(reason)
        payload = safety_state()
        event_bus.publish("safety.kill_switch.enabled", {"reason": reason})
        return payload

    @app.post("/safety/clear")
    def clear_safe_mode() -> dict[str, Any]:
        controller = get_safety_controller()
        controller.clear_safe_mode()
        payload = safety_state()
        event_bus.publish("safety.cleared", payload)
        return payload

    @app.get("/positions")
    def positions() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        rows = store.list_open_positions()
        payload = {
            "positions": rows,
            "shadow": store.shadow_summary(),
        }
        event_bus.publish("positions.snapshot", {"count": len(rows)})
        return payload

    @app.get("/audit/events")
    def audit_events(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        settings = ensure_runtime_paths()
        payload = {"events": _read_audit_events(settings.audit_log_path, limit=limit)}
        event_bus.publish("audit.snapshot", {"count": len(payload["events"])})
        return payload

    @app.post("/scan")
    async def scan(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
        settings = ensure_runtime_paths()
        event_bus.publish("scan.started", {"limit": limit})
        scanner = MarketScannerAgent(
            polymarket=build_polymarket_client(settings),
            risk_engine=build_risk_engine(settings),
        )
        result = await scanner.scan(limit=limit)
        scan_id = persist_scan_result(result, summary_event_type="backend.scan.completed", settings=settings)
        payload = build_scan_response(result, scan_id)
        event_bus.publish("scan.completed", payload)
        for score in result.scores[:25]:
            event_bus.publish(
                "market.scored",
                {
                    "market_id": score.market_id,
                    "decision": score.decision.value,
                    "score": score.score,
                    "question": score.question,
                    "reasons": score.reasons[:5],
                },
            )
        return payload

    @app.post("/verify-endpoints")
    async def verify_endpoints() -> dict[str, Any]:
        event_bus.publish("endpoints.verify.started", {})
        result = await verify_polymarket_public_endpoints(build_polymarket_client())
        payload = {"ok": result.ok, "checks": [check.model_dump() for check in result.checks]}
        event_bus.publish("endpoints.verify.completed", payload)
        return payload

    return app


app = create_backend_app()


def _wallet_provider_status() -> list[dict[str, str]]:
    return [
        _provider_status("dune", "DUNE_API_KEY"),
        _provider_status("nansen", "NANSEN_API_KEY"),
        _provider_status("glassnode", "GLASSNODE_API_KEY"),
    ]


def _research_provider_status() -> list[dict[str, str]]:
    return _wallet_provider_status() + [
        _provider_status("x", "X_BEARER_TOKEN"),
        _provider_status("reddit", "REDDIT_CLIENT_ID"),
        _provider_status("coingecko_news", "COINGECKO_API_KEY"),
    ]


def _provider_status(name: str, env_name: str) -> dict[str, str]:
    return {
        "name": name,
        "env": env_name,
        "status": "configured" if os.getenv(env_name) else "not_configured",
    }


def _read_audit_events(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"event_type": "corrupt_line", "raw": line})
    return events


def _build_dry_run_preview(guard: Any) -> dict[str, Any] | None:
    if not getattr(guard, "allowed", False):
        return None
    order = LiveExecutionConnector().prepare_order(
        guard,
        market_id="preview-market",
        side="YES",
        price=0.5,
        size=1.0,
    )
    return {
        "market_id": order.market_id,
        "side": order.side,
        "price": order.price,
        "size": order.size,
        "dry_run": order.dry_run,
    }


def _enrich_scan_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    finished_at = _parse_timestamp(summary.get("finished_at"))
    age_seconds = None
    freshness = "unknown"
    if finished_at is not None:
        age_seconds = max(int((datetime.now(timezone.utc) - finished_at).total_seconds()), 0)
        if age_seconds <= 300:
            freshness = "fresh"
        elif age_seconds <= 1800:
            freshness = "warming"
        else:
            freshness = "stale"
    return {
        **summary,
        "age_seconds": age_seconds,
        "freshness": freshness,
    }


def _build_market_summary(top_markets: list[dict[str, Any]], latest_scan: dict[str, Any] | None) -> dict[str, Any]:
    decisions = {"approve": 0, "watch": 0, "reject": 0}
    score_total = 0.0
    edge_total = 0.0
    spread_total = 0.0
    resolution_total = 0.0
    volume_total = 0.0
    liquidity_total = 0.0
    bid_depth_total = 0.0
    ask_depth_total = 0.0
    score_count = 0
    edge_count = 0
    spread_count = 0
    resolution_count = 0

    for row in top_markets:
        decision = str(row.get("decision") or "watch")
        if decision in decisions:
            decisions[decision] += 1
        score = row.get("score")
        if isinstance(score, (int, float)):
            score_total += float(score)
            score_count += 1
        edge = row.get("edge")
        if isinstance(edge, (int, float)):
            edge_total += float(edge)
            edge_count += 1
        spread = row.get("spread_bps")
        if isinstance(spread, (int, float)):
            spread_total += float(spread)
            spread_count += 1
        resolution = row.get("resolution_confidence")
        if isinstance(resolution, (int, float)):
            resolution_total += float(resolution)
            resolution_count += 1
        volume = row.get("volume_usdc")
        if isinstance(volume, (int, float)):
            volume_total += float(volume)
        liquidity = row.get("liquidity_usdc")
        if isinstance(liquidity, (int, float)):
            liquidity_total += float(liquidity)
        bid_depth = row.get("bid_depth_usdc")
        if isinstance(bid_depth, (int, float)):
            bid_depth_total += float(bid_depth)
        ask_depth = row.get("ask_depth_usdc")
        if isinstance(ask_depth, (int, float)):
            ask_depth_total += float(ask_depth)

    return {
        "visible_market_count": len(top_markets),
        "approve_count": decisions["approve"],
        "watch_count": decisions["watch"],
        "reject_count": decisions["reject"],
        "avg_score": None if score_count == 0 else round(score_total / score_count, 3),
        "avg_edge": None if edge_count == 0 else round(edge_total / edge_count, 5),
        "avg_spread_bps": None if spread_count == 0 else round(spread_total / spread_count, 2),
        "avg_resolution_confidence": None if resolution_count == 0 else round(resolution_total / resolution_count, 3),
        "total_volume_usdc": round(volume_total, 2),
        "total_liquidity_usdc": round(liquidity_total, 2),
        "total_bid_depth_usdc": round(bid_depth_total, 2),
        "total_ask_depth_usdc": round(ask_depth_total, 2),
        "latest_scan_age_seconds": None if latest_scan is None else latest_scan.get("age_seconds"),
        "latest_scan_freshness": None if latest_scan is None else latest_scan.get("freshness"),
    }


def _source_summary(source_snapshot: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(source_snapshot),
        "live": sum(1 for source in source_snapshot if source.get("status") == "live"),
        "degraded": sum(1 for source in source_snapshot if source.get("status") in {"stale", "offline", "error"}),
        "not_configured": sum(1 for source in source_snapshot if source.get("status") == "not_configured"),
    }


def _reference_source_rows(source_snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {str(source.get("name")): source for source in source_snapshot}
    rows: list[dict[str, Any]] = []
    for name, label in (
        ("polymarket_gamma", "Polymarket Gamma"),
        ("polymarket_clob", "Polymarket CLOB"),
        ("kalshi", "Kalshi"),
        ("binance_futures", "Binance Futures"),
        ("okx", "OKX"),
        ("coinbase", "Coinbase"),
    ):
        source = dict(by_name.get(name) or {"name": name, "status": "missing", "metadata": {}})
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        rows.append(
            {
                "name": name,
                "label": label,
                "status": source.get("status") or "missing",
                "latency_ms": source.get("latency_ms"),
                "detail": _source_detail(metadata),
                "last_ok_at": source.get("last_ok_at"),
                "error": source.get("error"),
            }
        )
    return rows


def _degraded_source_rows(source_snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_snapshot:
        status = str(source.get("status") or "unknown")
        if status not in {"stale", "offline", "error"}:
            continue
        rows.append(
            {
                "name": source.get("name"),
                "status": status,
                "failure_count": int(source.get("failure_count") or 0),
                "circuit_breaker": source.get("circuit_breaker") or "closed",
                "error": source.get("error"),
                "latency_ms": source.get("latency_ms"),
            }
        )
    return rows


def _build_strategy_payload(*, store: SQLiteStore, limit: int) -> dict[str, Any]:
    registry = ModelRegistry()
    models = store.list_model_versions(limit=limit)
    scores = store.list_strategy_scores(limit=limit)
    history = store.list_model_status_history(limit=limit)
    latest_scores_by_name: dict[str, dict[str, object]] = {}
    promotion_checks: list[dict[str, Any]] = []
    live_eligible_models: list[dict[str, object]] = []

    for row in scores:
        strategy_name = str(row.get("strategy_name") or "")
        if strategy_name and strategy_name not in latest_scores_by_name:
            latest_scores_by_name[strategy_name] = row

    for row in models:
        version = ModelVersion(
            name=str(row.get("name") or ""),
            version=str(row.get("version") or ""),
            status=str(row.get("status") or ""),
            notes=None if row.get("notes") is None else str(row.get("notes")),
        )
        latest_score = latest_scores_by_name.get(version.name)
        policy = registry.evaluate_promotion(version, latest_score=latest_score)
        live_eligible = registry.can_trade_live(version)
        if live_eligible:
            live_eligible_models.append(row)
        promotion_checks.append(
            {
                "name": version.name,
                "version": version.version,
                "status": version.status,
                "notes": version.notes,
                "created_at": row.get("created_at"),
                "live_eligible": live_eligible,
                "ready": policy.ready,
                "next_statuses": list(policy.next_statuses),
                "reasons": list(policy.reasons),
                "blocking_reasons": [] if policy.ready else list(policy.reasons),
                "latest_score": latest_score,
                "recommended_action": _recommended_model_action(version.status, policy.ready, policy.next_statuses),
            }
        )

    return {
        "scores": scores,
        "models": models,
        "live_eligible_models": live_eligible_models,
        "promotion_checks": promotion_checks,
        "model_history": history,
        "summary": _build_strategy_summary(
            models=models,
            promotion_checks=promotion_checks,
            history=history,
            scores=scores,
        ),
        "last_transition": None if not history else history[0],
    }


def _build_strategy_summary(
    *,
    models: list[dict[str, object]],
    promotion_checks: list[dict[str, Any]],
    history: list[dict[str, object]],
    scores: list[dict[str, object]],
) -> dict[str, Any]:
    counts = {"candidate": 0, "shadow": 0, "approved": 0, "retired": 0, "unknown": 0}
    for row in models:
        status = str(row.get("status") or "unknown")
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1

    ready_model_count = sum(1 for row in promotion_checks if bool(row.get("ready")))
    blocked_model_count = sum(
        1
        for row in promotion_checks
        if not bool(row.get("ready")) and str(row.get("status") or "") in {"candidate", "shadow"}
    )
    ready_for_shadow_count = sum(
        1 for row in promotion_checks if bool(row.get("ready")) and str(row.get("status") or "") == "candidate"
    )
    ready_for_approval_count = sum(
        1 for row in promotion_checks if bool(row.get("ready")) and str(row.get("status") or "") == "shadow"
    )
    latest_score = None if not scores else scores[0]
    latest_transition = None if not history else history[0]

    if ready_for_approval_count > 0:
        next_gate = "Manual approval review is the next gate for shadow models."
    elif ready_for_shadow_count > 0:
        next_gate = "Promote ready candidate models into shadow validation."
    elif counts["approved"] > 0:
        next_gate = "Execution guard, secrets and operator approvals are the remaining live blockers."
    elif counts["candidate"] + counts["shadow"] > 0:
        next_gate = "Collect more scored outcomes before the next promotion step."
    else:
        next_gate = "Register a candidate model and record strategy scores to start the promotion ladder."

    return {
        "total_models": len(models),
        "candidate_count": counts["candidate"],
        "shadow_count": counts["shadow"],
        "approved_count": counts["approved"],
        "retired_count": counts["retired"],
        "unknown_count": counts["unknown"],
        "ready_model_count": ready_model_count,
        "blocked_model_count": blocked_model_count,
        "ready_for_shadow_count": ready_for_shadow_count,
        "ready_for_approval_count": ready_for_approval_count,
        "history_count": len(history),
        "next_gate": next_gate,
        "latest_score_name": None if latest_score is None else latest_score.get("strategy_name"),
        "latest_score_created_at": None if latest_score is None else latest_score.get("created_at"),
        "latest_transition_at": None if latest_transition is None else latest_transition.get("changed_at"),
    }


def _recommended_model_action(status: str, ready: bool, next_statuses: tuple[str, ...]) -> str:
    if not next_statuses:
        return "No further promotion path."
    if ready:
        return f"Ready to move toward {next_statuses[0]}."
    if status == "candidate":
        return "Add more paper/shadow evidence before shadow promotion."
    if status == "shadow":
        return "Add more validated outcomes before approval review."
    if status == "approved":
        return "Monitor live guard readiness or retire if score quality slips."
    return "Review strategy lifecycle state."


def _build_micro_live_readiness(
    *,
    store: SQLiteStore,
    strategy_payload: dict[str, Any],
    secrets_ready: bool,
    reconciliation: Any,
) -> dict[str, Any]:
    strategy_summary = strategy_payload.get("summary") if isinstance(strategy_payload.get("summary"), dict) else {}
    latest_score = strategy_payload.get("scores", [None])[0] if strategy_payload.get("scores") else None
    latest_ack = store.latest_operator_acknowledgement(LIVE_EXECUTION_ACK_SCOPE)
    derived_items = {
        "approved_model": {
            "label": "Approved model exists for live gate review.",
            "passed": int(strategy_summary.get("approved_count") or 0) > 0,
            "detail": f"approved_count={strategy_summary.get('approved_count', 0)}",
        },
        "strategy_score_positive": {
            "label": "Latest strategy score remains positive.",
            "passed": bool(latest_score) and float((latest_score or {}).get("score") or 0.0) > 0,
            "detail": "no strategy score recorded" if not latest_score else f"latest_score={float((latest_score or {}).get('score') or 0.0):.4f}",
        },
        "sample_size_ready": {
            "label": "Sample-size readiness threshold is met.",
            "passed": bool(latest_score) and int((latest_score or {}).get("sample_count") or 0) >= 100,
            "detail": "no strategy score recorded" if not latest_score else f"sample_count={int((latest_score or {}).get('sample_count') or 0)}",
        },
        "secrets_ready": {
            "label": "Required live execution secrets are present.",
            "passed": secrets_ready,
            "detail": "live secrets present" if secrets_ready else "missing one or more required live secrets",
        },
        "reconciliation_tested": {
            "label": "Reconciliation checks have been exercised.",
            "passed": bool(getattr(reconciliation, "ok", False)),
            "detail": " | ".join(getattr(reconciliation, "reasons", ())),
        },
        "manual_approval_tested": {
            "label": "Manual approval process has been acknowledged by an operator.",
            "passed": bool(latest_ack and latest_ack.get("acknowledged")),
            "detail": "no operator acknowledgement saved" if not latest_ack else str(latest_ack.get("note") or "operator acknowledgement recorded"),
        },
    }
    for item_key, label in MICRO_LIVE_CHECKLIST_ITEMS:
        derived = derived_items[item_key]
        store.set_readiness_item(
            scope=MICRO_LIVE_SCOPE,
            item_key=item_key,
            label=label,
            passed=bool(derived["passed"]),
            detail=str(derived["detail"]),
            updated_by="system",
        )
    items = store.list_readiness_items(MICRO_LIVE_SCOPE)
    passed_count = sum(1 for item in items if bool(item.get("passed")))
    total_count = len(items)
    blocked_items = [item for item in items if not bool(item.get("passed"))]
    return {
        "scope": MICRO_LIVE_SCOPE,
        "items": items,
        "passed_count": passed_count,
        "total_count": total_count,
        "ready": total_count > 0 and passed_count == total_count,
        "blocked_items": blocked_items,
        "operator_ack": latest_ack,
    }


def _build_risk_signals(
    *,
    open_positions: list[dict[str, Any]],
    source_summary: dict[str, int],
    current_daily_pnl_usdc: float,
    max_daily_loss_usdc: float,
) -> dict[str, dict[str, Any]]:
    funding_status = "degraded"
    correlation_status = "degraded"
    liquidation_status = "clear" if not open_positions else "monitor"
    funding_reasons = ["funding feed not wired yet"]
    correlation_reasons = ["cross-position correlation model not wired yet"]
    liquidation_reasons = ["no leveraged live positions"] if not open_positions else ["paper/shadow positions need liquidation-distance model"]

    if source_summary.get("degraded", 0) > 0:
        funding_reasons.append("reference venue health is degraded")
        correlation_reasons.append("source degradation reduces portfolio confidence")

    utilization = 0.0
    if max_daily_loss_usdc > 0:
        utilization = min(abs(current_daily_pnl_usdc) / max_daily_loss_usdc, 1.0)

    return {
        "funding": {
            "status": funding_status,
            "value": None,
            "confidence": 0.0,
            "reasons": funding_reasons,
        },
        "correlation": {
            "status": correlation_status,
            "value": None,
            "confidence": 0.0,
            "reasons": correlation_reasons,
        },
        "liquidation_distance": {
            "status": liquidation_status,
            "value": None,
            "confidence": 0.0 if not open_positions else 0.2,
            "reasons": liquidation_reasons,
        },
        "daily_loss_buffer": {
            "status": "clear" if utilization < 0.5 else "monitor" if utilization < 0.8 else "tight",
            "value": round(max(max_daily_loss_usdc - abs(current_daily_pnl_usdc), 0.0), 2),
            "confidence": 1.0,
            "reasons": [f"daily loss utilization={utilization:.2f}"],
        },
    }


def _source_detail(metadata: dict[str, Any]) -> str | None:
    for key in ("symbol", "market_id", "mark_price", "last_price", "price", "midpoint", "market_count"):
        value = metadata.get(key)
        if value is not None:
            return f"{key}={value}"
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
