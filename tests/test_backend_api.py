from fastapi.testclient import TestClient

from superajan12.backend_api import app


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
    assert "top_markets" in markets.json()
    assert "latest_scan" in markets.json()

    assert wallet.status_code == 200
    assert "providers" in wallet.json()
    assert "events" in wallet.json()

    assert strategy.status_code == 200
    assert "scores" in strategy.json()
    assert "models" in strategy.json()

    assert risk.status_code == 200
    risk_payload = risk.json()
    assert "capital" in risk_payload
    assert "execution" in risk_payload
    assert "safety" in risk_payload

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
