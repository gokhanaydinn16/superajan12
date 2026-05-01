from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from superajan12.agents.risk import RiskEngine
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.audit import AuditLogger
from superajan12.config import get_settings
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.endpoint_check import verify_polymarket_public_endpoints
from superajan12.events import event_bus
from superajan12.health import build_default_health_registry
from superajan12.reporting import Reporter
from superajan12.storage import SQLiteStore


def create_backend_app() -> FastAPI:
    app = FastAPI(title="SuperAjan12 Backend", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        settings = get_settings()
        return {
            "ok": True,
            "mode": settings.mode,
            "live_trading": "disabled",
            "database": str(settings.sqlite_path),
        }

    @app.get("/sources")
    def sources() -> dict[str, Any]:
        registry = build_default_health_registry()
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
        settings = get_settings()
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

    @app.post("/scan")
    async def scan(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, Any]:
        settings = get_settings()
        event_bus.publish("scan.started", {"limit": limit})
        client = PolymarketClient(
            gamma_base_url=str(settings.polymarket_gamma_base_url),
            clob_base_url=str(settings.polymarket_clob_base_url),
        )
        risk_engine = RiskEngine(
            max_market_risk_usdc=settings.max_market_risk_usdc,
            max_daily_loss_usdc=settings.max_daily_loss_usdc,
            min_volume_usdc=settings.min_volume_usdc,
            max_spread_bps=settings.max_spread_bps,
            min_liquidity_usdc=settings.min_liquidity_usdc,
        )
        scanner = MarketScannerAgent(polymarket=client, risk_engine=risk_engine)
        result = await scanner.scan(limit=limit)
        scan_id = SQLiteStore(settings.sqlite_path).save_scan(result)
        AuditLogger(settings.audit_log_path).record(
            "backend.scan.completed",
            {"scan_id": scan_id, **result.model_dump(mode="json")},
        )
        payload = {
            "scan_id": scan_id,
            "score_count": len(result.scores),
            "idea_count": len(result.ideas),
            "paper_position_count": len(result.paper_positions),
        }
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
        settings = get_settings()
        event_bus.publish("endpoints.verify.started", {})
        client = PolymarketClient(
            gamma_base_url=str(settings.polymarket_gamma_base_url),
            clob_base_url=str(settings.polymarket_clob_base_url),
        )
        result = await verify_polymarket_public_endpoints(client)
        payload = {"ok": result.ok, "checks": [check.model_dump() for check in result.checks]}
        event_bus.publish("endpoints.verify.completed", payload)
        return payload

    return app


app = create_backend_app()
