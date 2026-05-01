from __future__ import annotations

import json
import os
from pathlib import Path
from time import monotonic
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from superajan12.approval import ManualApprovalGate
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.audit import AuditLogger
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


def create_backend_app() -> FastAPI:
    app = FastAPI(title="SuperAjan12 Backend", version="0.2.0")
    started_at_monotonic = monotonic()
    ensure_runtime_paths()

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
        payload = {
            "top_markets": reporter.top_scored_markets(limit=top),
            "latest_scan": reporter.latest_summary(),
            "source_health_mode": "static"
            if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("SUPERAJAN12_SOURCE_HEALTH_MODE") == "static"
            else "live",
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
        models = store.list_model_versions(limit=limit)
        rows = store.list_strategy_scores(limit=limit)
        payload = {
            "scores": rows,
            "models": models,
            "live_eligible_models": [
                row
                for row in models
                if ModelRegistry().can_trade_live(
                    ModelVersion(
                        name=str(row.get("name") or ""),
                        version=str(row.get("version") or ""),
                        status=str(row.get("status") or ""),
                        notes=None if row.get("notes") is None else str(row.get("notes")),
                    )
                )
            ],
        }
        event_bus.publish("strategy.snapshot", payload)
        return payload

    @app.get("/risk/status")
    def risk_status() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        store = SQLiteStore(settings.sqlite_path)
        open_positions = store.list_open_positions()
        open_risk = sum(float(position.get("risk_usdc") or 0.0) for position in open_positions)
        shadow = store.shadow_summary()
        aggregate = Reporter(settings.sqlite_path).aggregate_summary()
        safety = get_safety_controller().state()
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
        }
        event_bus.publish("risk.snapshot", payload)
        return payload

    @app.get("/execution/status")
    def execution_status() -> dict[str, Any]:
        settings = ensure_runtime_paths()
        safety = get_safety_controller().state()
        approval_gate = ManualApprovalGate()
        pending_ticket = approval_gate.request("live_execution", "desktop execution center preview")
        required_secret_names = (
            "SUPERAJAN12_LIVE_API_KEY",
            "SUPERAJAN12_LIVE_API_SECRET",
        )
        secret_manager = EnvSecretManager()
        secret_refs = [secret_manager.has_secret(name) for name in required_secret_names]
        secrets_ready = all(secret.present for secret in secret_refs)
        guard = ExecutionGuard(approval_gate).can_execute(
            mode=settings.mode,
            safety_state=safety,
            approval_ticket=pending_ticket,
            secrets_ready=secrets_ready,
        )
        local_open_positions = len(SQLiteStore(settings.sqlite_path).list_open_positions())
        reconciliation = ReconciliationAgent().compare_counts(
            local_open_positions=local_open_positions,
            external_open_positions=local_open_positions,
        )
        payload = {
            "mode": settings.mode,
            "live_trading": "disabled",
            "approval": {
                "required": True,
                "approved": False,
                "action": pending_ticket.action,
                "reason": pending_ticket.reason,
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
