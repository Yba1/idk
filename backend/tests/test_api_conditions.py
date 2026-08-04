from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_conditions_endpoint_returns_all_fourteen_conditions():
    response = client.get("/conditions")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 14
    scalp = next(c for c in body if c["name"] == "Scalp angiosarcoma")
    assert scalp["rarity"] == "rare"
    assert scalp["atlas_label"] == "Precentral Gyrus, Postcentral Gyrus"
