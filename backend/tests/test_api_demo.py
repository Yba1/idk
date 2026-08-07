from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.registry import get_services

client = TestClient(app)


def _reset_fake_profile(monkeypatch):
    monkeypatch.setenv("NEULIT_PROFILE", "fake")
    get_services.cache_clear()


def test_demo_contrast_endpoint_returns_naive_and_weighted_lists(monkeypatch):
    _reset_fake_profile(monkeypatch)

    response = client.get("/demo-contrast")

    assert response.status_code == 200
    body = response.json()
    assert len(body["naive"]) == 5
    assert len(body["weighted"]) == 5
    assert body["query"]
    for paper in body["naive"] + body["weighted"]:
        assert set(paper.keys()) == {"pmid", "title", "condition", "rarity"}


def test_demo_contrast_rare_case_pmid_is_a_rare_paper_from_the_weighted_list(monkeypatch):
    _reset_fake_profile(monkeypatch)

    body = client.get("/demo-contrast").json()

    if body["rare_case_pmid"]:
        weighted_by_pmid = {p["pmid"]: p for p in body["weighted"]}
        assert weighted_by_pmid[body["rare_case_pmid"]]["rarity"] == "rare"
