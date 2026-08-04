from unittest.mock import MagicMock, patch
import pytest
import numpy as np
from fastapi import Response
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


@patch("backend.api.routes.atlas.view_img_on_surf")
@patch("backend.api.routes.atlas.load_img")
@patch("backend.api.routes.atlas._load_atlas")
def test_atlas_endpoint_returns_html_for_known_condition(mock_load_atlas, mock_load_img, mock_view_img):
    mock_atlas = MagicMock()
    mock_atlas.labels = [
        "Background",
        "Frontal Pole",
        "Precentral Gyrus",
        "Postcentral Gyrus",
    ]
    mock_load_atlas.return_value = mock_atlas

    mock_img = MagicMock()
    mock_img.get_fdata.return_value = np.zeros((10, 10, 10))
    mock_img.affine = np.eye(4)
    mock_load_img.return_value = mock_img

    mock_view_obj = MagicMock()
    mock_view_obj.html = "<!DOCTYPE html><html><body>Test</body></html>"
    mock_view_img.return_value = mock_view_obj

    response = client.get("/atlas/Scalp%20angiosarcoma")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text


def test_atlas_endpoint_returns_fallback_for_unknown_condition():
    response = client.get("/atlas/NonexistentCondition")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "Atlas view unavailable" in response.text
    assert "not a diagnostic read" in response.text


@patch("backend.api.routes.atlas.view_img_on_surf")
@patch("backend.api.routes.atlas.load_img")
@patch("backend.api.routes.atlas._load_atlas")
def test_atlas_endpoint_url_decodes_condition_name(mock_load_atlas, mock_load_img, mock_view_img):
    mock_atlas = MagicMock()
    mock_atlas.labels = ["Background", "Precentral Gyrus"]
    mock_load_atlas.return_value = mock_atlas

    mock_img = MagicMock()
    mock_img.get_fdata.return_value = np.zeros((10, 10, 10))
    mock_img.affine = np.eye(4)
    mock_load_img.return_value = mock_img

    mock_view_obj = MagicMock()
    mock_view_obj.html = "<!DOCTYPE html><html></html>"
    mock_view_img.return_value = mock_view_obj

    response = client.get("/atlas/Scalp%20angiosarcoma")
    assert response.status_code == 200


@patch("backend.api.routes.atlas.view_img_on_surf")
@patch("backend.api.routes.atlas._load_atlas")
def test_default_atlas_endpoint_returns_html(mock_load_atlas, mock_view_img):
    mock_atlas = MagicMock()
    mock_atlas.maps = MagicMock()
    mock_load_atlas.return_value = mock_atlas

    mock_view_obj = MagicMock()
    mock_view_obj.html = "<!DOCTYPE html><html><body>Atlas</body></html>"
    mock_view_img.return_value = mock_view_obj

    with patch("backend.api.routes.atlas.load_img") as mock_load_img:
        mock_img = MagicMock()
        mock_img.get_fdata.return_value = np.random.randint(0, 20, (10, 10, 10))
        mock_load_img.return_value = mock_img

        response = client.get("/atlas")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text


@patch("backend.api.routes.atlas.view_img_on_surf")
@patch("backend.api.routes.atlas.load_img")
@patch("backend.api.routes.atlas._load_atlas")
def test_atlas_endpoint_falls_back_to_subcortical_atlas(mock_load_atlas, mock_load_img, mock_view_img):
    mock_atlas_cort = MagicMock()
    mock_atlas_cort.labels = ["Background", "Other Region"]

    mock_atlas_sub = MagicMock()
    mock_atlas_sub.labels = ["Background", "Pallidum"]

    mock_load_atlas.side_effect = [mock_atlas_cort, mock_atlas_sub]

    mock_img = MagicMock()
    mock_img.get_fdata.return_value = np.zeros((10, 10, 10))
    mock_img.affine = np.eye(4)
    mock_load_img.return_value = mock_img

    mock_view_obj = MagicMock()
    mock_view_obj.html = "<!DOCTYPE html><html></html>"
    mock_view_img.return_value = mock_view_obj

    response = client.get("/atlas/Progressive%20supranuclear%20palsy")

    assert response.status_code == 200
    assert "Pallidum" in mock_load_atlas.call_args_list[1][0][0] or "sub" in str(mock_load_atlas.call_args_list[1])


@patch("backend.api.routes.atlas.view_img_on_surf")
@patch("backend.api.routes.atlas.load_img")
@patch("backend.api.routes.atlas._load_atlas")
def test_query_atlas_endpoint_colors_only_cited_lobes(mock_load_atlas, mock_load_img, mock_view_img):
    mock_atlas = MagicMock()
    mock_atlas.maps = MagicMock()
    mock_atlas.labels = [
        "Background",
        "Frontal Pole",
        "Precentral Gyrus",
        "Superior Temporal Gyrus",
        "Lateral Occipital Cortex",
    ]
    mock_load_atlas.return_value = mock_atlas

    mock_img = MagicMock()
    mock_img.get_fdata.return_value = np.array([0, 1, 2, 3, 4] * 20).reshape(10, 10, 1)
    mock_img.affine = np.eye(4)
    mock_load_img.return_value = mock_img

    mock_view_obj = MagicMock()
    mock_view_obj.html = "<!DOCTYPE html><html><head></head><body>Test</body></html>"
    mock_view_img.return_value = mock_view_obj

    response = client.get(
        "/atlas/query",
        params={"conditions": "Scalp angiosarcoma,Dementia with Lewy bodies"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "<!DOCTYPE html>" in response.text
    # Scalp angiosarcoma resolves to Precentral Gyrus (frontal); Dementia with
    # Lewy bodies resolves to Lateral Occipital Cortex (occipital). Both
    # lobe colors must be baked into the injected anchor map; temporal
    # (not cited) must not be.
    assert "#a78bfa" in response.text.lower()  # frontal
    assert "#c084fc" in response.text.lower()  # occipital
    assert "#f472b6" not in response.text.lower()  # temporal, not cited


def test_query_atlas_endpoint_falls_back_to_default_for_no_conditions():
    with patch("backend.api.routes.atlas.get_default_atlas") as mock_default:
        mock_default.return_value = Response(content="<html>default</html>", media_type="text/html")
        response = client.get("/atlas/query", params={"conditions": ""})

    assert response.status_code == 200
    assert response.text == "<html>default</html>"


def test_query_atlas_endpoint_falls_back_to_default_for_unresolvable_conditions():
    with patch("backend.api.routes.atlas.get_default_atlas") as mock_default:
        mock_default.return_value = Response(content="<html>default</html>", media_type="text/html")
        response = client.get("/atlas/query", params={"conditions": "Nonexistent Condition"})

    assert response.status_code == 200
    assert response.text == "<html>default</html>"


def test_query_atlas_endpoint_does_not_crash_on_atlas_error():
    with patch("backend.api.routes.atlas._load_atlas", side_effect=RuntimeError("boom")):
        response = client.get(
            "/atlas/query",
            params={"conditions": "Scalp angiosarcoma"},
        )

    assert response.status_code == 200
    assert "Atlas view unavailable" in response.text
    assert "not a diagnostic read" in response.text
