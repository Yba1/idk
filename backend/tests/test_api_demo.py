from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_demo_contrast

client = TestClient(app)


def test_demo_contrast_endpoint_returns_naive_and_weighted_with_metadata():
    fake_result = {
        "naive_top5": ["22567182"],
        "weighted_top5": ["40902156"],
        "rare_case_pmid": "40902156",
    }
    app.dependency_overrides[get_demo_contrast] = lambda: fake_result
    try:
        response = client.get("/demo-contrast")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["rare_case_pmid"] == "40902156"
    assert body["weighted"][0]["pmid"] == "40902156"
    assert body["weighted"][0]["condition"] == "Scalp angiosarcoma"
    assert body["naive"][0]["pmid"] == "22567182"
    assert body["naive"][0]["condition"] == "Creutzfeldt-Jakob disease"
