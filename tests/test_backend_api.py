from fastapi.testclient import TestClient

from superajan12.backend_api import app
from superajan12.config import get_settings
from superajan12.storage import SQLiteStore
from superajan12.strategy import StrategyScore


def test_backend_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["live_trading"] == "disabled"


def test_backend_sources_use_explicit_statuses() -> None:
    client = TestClient(app)

    response = client.get("/sources")

    assert response.status_code == 200
    payload = response.json()
    assert "sources" in payload
    assert payload["sources"]
    assert {source["status"] for source in payload["sources"]} <= {
        "not_configured",
        "loading",
        "live",
        "stale",
        "offline",
        "error",
    }
    for source in payload["sources"]:
        assert "failure_count" in source
        assert "circuit_breaker" in source


def test_backend_command_center_endpoints_have_expected_shapes() -> None:
    client = TestClient(app)

    research = client.get("/research/tasks")
    markets = client.get("/markets")
    wallet = client.get("/wallet/events")
    strategy = client.get("/strategy/scores")
    risk = client.get("/risk/status")
    execution = client.get("/execution/status")
    system_health = client.get("/system/health")
    positions = client.get("/positions")
    audit = client.get("/audit/events")
    market_state = client.get("/market-state/validate", params={"market_id": "missing", "token_id": "missing"})

    assert research.status_code == 200
    assert "tasks" in research.json()
    assert "providers" in research.json()

    assert markets.status_code == 200
    markets_payload = markets.json()
    assert "top_markets" in markets_payload
    assert "latest_scan" in markets_payload
    assert "market_summary" in markets_payload
    assert "source_summary" in markets_payload
    assert "reference_sources" in markets_payload
    assert markets_payload["source_summary"]["total"] >= 0
    assert len(markets_payload["reference_sources"]) == 6

    assert wallet.status_code == 200
    assert "providers" in wallet.json()
    assert "events" in wallet.json()

    assert strategy.status_code == 200
    strategy_payload = strategy.json()
    assert "scores" in strategy_payload
    assert "models" in strategy_payload
    assert "live_eligible_models" in strategy_payload
    assert "promotion_checks" in strategy_payload
    assert "model_history" in strategy_payload
    assert "summary" in strategy_payload
    assert "last_transition" in strategy_payload
    assert "next_gate" in strategy_payload["summary"]
    assert "ready_model_count" in strategy_payload["summary"]
    assert "blocked_model_count" in strategy_payload["summary"]

    assert risk.status_code == 200
    risk_payload = risk.json()
    assert "capital" in risk_payload
    assert "execution" in risk_payload
    assert "safety" in risk_payload
    assert "risk_signals" in risk_payload
    assert "source_health_gate" in risk_payload
    assert "funding" in risk_payload["risk_signals"]
    assert "correlation" in risk_payload["risk_signals"]
    assert "liquidation_distance" in risk_payload["risk_signals"]
    assert "daily_loss_buffer" in risk_payload["risk_signals"]

    assert execution.status_code == 200
    execution_payload = execution.json()
    assert "approval" in execution_payload
    assert "secrets" in execution_payload
    assert "guard" in execution_payload
    assert execution_payload["live_trading"] == "disabled"

    assert system_health.status_code == 200
    system_payload = system_health.json()
    assert system_payload["ok"] is True
    assert "backend" in system_payload
    assert "database" in system_payload
    assert "sources" in system_payload
    assert "open_circuit_breakers" in system_payload["sources"]
    assert "degraded_sources" in system_payload["sources"]

    assert positions.status_code == 200
    assert "positions" in positions.json()
    assert "shadow" in positions.json()

    assert audit.status_code == 200
    assert "events" in audit.json()
    assert market_state.status_code == 200
    assert market_state.json()["ok"] is False


def test_backend_safety_state_endpoints_change_runtime_state() -> None:
    client = TestClient(app)

    client.post("/safety/clear")
    start = client.get("/safety/state")
    assert start.status_code == 200
    assert "safe_mode" in start.json()

    enabled = client.post("/safety/enable-safe-mode", params={"reason": "test"})
    assert enabled.status_code == 200
    assert enabled.json()["safe_mode"] is True
    assert enabled.json()["kill_switch"] is False

    kill = client.post("/safety/enable-kill-switch", params={"reason": "emergency"})
    assert kill.status_code == 200
    assert kill.json()["safe_mode"] is True
    assert kill.json()["kill_switch"] is True

    cleared = client.post("/safety/clear")
    assert cleared.status_code == 200
    assert cleared.json()["safe_mode"] is False
    assert cleared.json()["kill_switch"] is False


def test_backend_health_creates_runtime_directories() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = client.get("/system/health").json()
    assert payload["database"]["parent_exists"] is True
    assert payload["audit_log"]["parent_exists"] is True


def test_strategy_model_transition_endpoint_updates_history(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "transition.sqlite3"
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_path))
    get_settings.cache_clear()
    store = SQLiteStore(sqlite_path)
    store.save_strategy_score(
        StrategyScore(
            strategy_name="baseline",
            sample_count=60,
            total_pnl_usdc=12.0,
            win_rate=0.61,
            avg_pnl_usdc=0.2,
            score=0.8,
        )
    )
    store.save_model_version(
        name="baseline",
        version="v1",
        status="candidate",
        notes="initial registration",
        change_reason="seed candidate",
        changed_by="test-suite",
    )

    client = TestClient(app)
    response = client.post(
        "/strategy/models/transition",
        json={
            "model_name": "baseline",
            "model_version": "v1",
            "status": "shadow",
            "notes": "paper evidence cleared",
            "changed_by": "test-suite",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["from_status"] == "candidate"
    assert payload["to_status"] == "shadow"
    strategy_payload = client.get("/strategy/scores").json()
    assert strategy_payload["last_transition"]["to_status"] == "shadow"
    get_settings.cache_clear()


def test_execution_operator_acknowledgement_endpoint_persists(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "execution.sqlite3"
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_path))
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/execution/operator-acknowledgement",
        json={
            "acknowledged": True,
            "acknowledged_by": "test-operator",
            "note": "manual review completed",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    operator_ack = payload["micro_live_readiness"]["operator_ack"]
    assert operator_ack["acknowledged"] is True
    assert operator_ack["acknowledged_by"] == "test-operator"
    assert operator_ack["note"] == "manual review completed"
    get_settings.cache_clear()
