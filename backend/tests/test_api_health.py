from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["ports"]) == {"retrieval", "llm", "memory", "ledger"}
    assert all(p["ok"] for p in body["ports"].values())
