"""Tests for the HTTP API, including the free/pro tier gate."""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import api.main
    importlib.reload(api.main)
    return TestClient(api.main.app)


@pytest.fixture
def gated_client(monkeypatch):
    """A deployment configured with one free and one pro key."""
    monkeypatch.setenv("EXERCISES_API_KEYS", "freekey:free,prokey:pro")
    monkeypatch.setenv("EXERCISES_REQUIRE_KEY", "1")
    import api.main
    importlib.reload(api.main)
    yield TestClient(api.main.app)
    monkeypatch.delenv("EXERCISES_API_KEYS")
    monkeypatch.delenv("EXERCISES_REQUIRE_KEY")
    importlib.reload(api.main)


def test_health(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert body["exercises"] == 1324


def test_facets_expose_filterable_values(client):
    facets = client.get("/v1/facets").json()
    assert "horizontal_push" in facets["pattern"]
    assert "full_gym" in facets["equipment_profile"]


def test_listing_filters_and_paginates(client):
    body = client.get("/v1/exercises",
                      params={"pattern": "squat", "role": "primary",
                              "limit": 5}).json()
    assert body["total"] > 5
    assert len(body["results"]) == 5
    assert all(e["pattern"] == "squat" for e in body["results"])
    assert "Gym visual" in body["attribution"]


def test_listing_returns_the_requested_language(client):
    body = client.get("/v1/exercises",
                      params={"language": "tr", "limit": 1}).json()
    result = body["results"][0]
    assert result["language"] == "tr"
    assert result["instruction_steps"]


def test_search_by_name(client):
    body = client.get("/v1/exercises", params={"q": "deadlift"}).json()
    assert body["total"] > 0
    assert all("deadlift" in e["name"].lower() for e in body["results"])


def test_unknown_equipment_profile_is_a_400(client):
    response = client.get("/v1/exercises",
                          params={"equipment_profile": "space_station"})
    assert response.status_code == 400


def test_single_exercise_and_404(client):
    assert client.get("/v1/exercises/0001").json()["id"] == "0001"
    assert client.get("/v1/exercises/nope").status_code == 404


def test_program_generation(client):
    body = client.post("/v1/programs", json={
        "goal": "hypertrophy", "level": "intermediate", "days_per_week": 4,
        "session_minutes": 60, "weeks": 4, "language": "tr", "seed": 1,
    }).json()
    assert len(body["weeks"]) == 4
    assert len(body["weeks"][0]["days"]) == 4
    assert body["weeks"][3]["is_deload"]


def test_program_rejects_an_invalid_request(client):
    assert client.post("/v1/programs", json={"days_per_week": 9}).status_code == 422


def test_free_tier_can_read_but_not_generate(gated_client):
    headers = {"X-API-Key": "freekey"}
    assert gated_client.get("/v1/exercises", headers=headers).status_code == 200
    response = gated_client.post("/v1/programs", json={}, headers=headers)
    assert response.status_code == 402


def test_pro_tier_can_generate(gated_client):
    response = gated_client.post("/v1/programs", json={"seed": 1},
                                 headers={"X-API-Key": "prokey"})
    assert response.status_code == 200


def test_missing_key_is_rejected_when_keys_are_required(gated_client):
    assert gated_client.get("/v1/exercises").status_code == 401
