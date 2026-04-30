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
