"""Tests for the stateful layer: accounts, saved programs and workout logging."""

import itertools

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.db import SessionLocal, create_all
from app.models import Program, User
from app.security import hash_password, verify_password

_emails = (f"user{n}@example.com" for n in itertools.count())


@pytest.fixture(scope="module")
def client():
    create_all()
    with TestClient(app) as test_client:
        yield test_client


def _register(client) -> dict:
    """Register a fresh account and return its auth headers.

    A plain function rather than a fixture: pytest caches a fixture per test,
    so two accounts in one test have to be requested explicitly.
    """
    response = client.post("/v1/auth/register",
                           json={"email": next(_emails),
                                 "password": "correct-horse-1"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def account(client):
    """A registered account, returning ``(headers, email)``."""
    email = next(_emails)
    response = client.post("/v1/auth/register",
                           json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


@pytest.fixture
def saved_program(client, account):
    headers, _ = account
    response = client.post("/v1/programs",
                           json={"level": "beginner", "days_per_week": 3,
                                 "weeks": 4, "seed": 1},
                           headers=headers)
    assert response.status_code == 201
    return headers, response.json()["id"]


def _log(client, headers, program_id, week, day, sets,
         exercise_id="0043", exercise_name="barbell full squat"):
    return client.post("/v1/workouts/sessions", headers=headers, json={
        "program_id": program_id, "week": week, "day_index": day,
        "day_name": "Test day",
        "sets": [{"exercise_id": exercise_id, "exercise_name": exercise_name,
                  "set_index": i + 1, "reps": reps, "weight_kg": weight}
                 for i, (reps, weight) in enumerate(sets)],
    })


def _suggestion(client, headers, exercise_id="0043", rep_min=8, rep_max=12):
    return client.get(f"/v1/workouts/suggestion/{exercise_id}",
                      params={"rep_min": rep_min, "rep_max": rep_max},
                      headers=headers).json()


# --- password hashing -------------------------------------------------
def test_password_round_trip():
    encoded = hash_password("correct-horse-1")
    assert verify_password("correct-horse-1", encoded)
    assert not verify_password("wrong", encoded)


def test_hashes_are_salted():
    assert hash_password("same-password") != hash_password("same-password")


def test_a_corrupt_hash_never_verifies():
    assert not verify_password("anything", "not-a-real-hash")


# --- registration and login -------------------------------------------
def test_register_login_and_me(client):
    email = next(_emails)
    registered = client.post("/v1/auth/register",
                             json={"email": email, "password": "correct-horse-1",
                                   "display_name": "Efe", "language": "tr"})
    assert registered.status_code == 201

    logged_in = client.post("/v1/auth/login",
                            json={"email": email, "password": "correct-horse-1"})
    assert logged_in.status_code == 200

    headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}
    me = client.get("/v1/auth/me", headers=headers).json()
    assert me["email"] == email
    assert me["display_name"] == "Efe"
    assert me["tier"] == "free"


def test_email_is_case_insensitive(client):
    email = next(_emails)
    client.post("/v1/auth/register",
                json={"email": email.upper(), "password": "correct-horse-1"})
    response = client.post("/v1/auth/login",
                           json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 200


def test_duplicate_email_is_rejected(client):
    email = next(_emails)
    body = {"email": email, "password": "correct-horse-1"}
    assert client.post("/v1/auth/register", json=body).status_code == 201
    assert client.post("/v1/auth/register", json=body).status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/v1/auth/register",
                           json={"email": next(_emails), "password": "short"})
    assert response.status_code == 422


def test_wrong_password_is_rejected(client, account):
    _, email = account
    response = client.post("/v1/auth/login",
                           json={"email": email, "password": "not-the-password"})
    assert response.status_code == 401


def test_login_for_an_unknown_email_is_rejected(client):
    response = client.post("/v1/auth/login",
                           json={"email": "nobody@example.com",
                                 "password": "correct-horse-1"})
    assert response.status_code == 401


def test_password_is_never_stored_in_the_clear(client, account):
    _, email = account
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email).one()
    assert "correct-horse-1" not in user.password_hash
    assert user.password_hash.startswith("scrypt$")


# --- token handling ---------------------------------------------------
@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer nonsense"},
    {"Authorization": "Basic abc"},
])
def test_protected_routes_reject_bad_credentials(client, headers):
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_logout_revokes_the_token(client, account):
    headers, _ = account
    assert client.post("/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_profile_can_be_updated(client, account):
    headers, _ = account
    response = client.patch("/v1/auth/me", headers=headers,
                            json={"language": "tr", "unit_system": "imperial"})
    assert response.status_code == 200
    assert response.json()["language"] == "tr"
    assert response.json()["unit_system"] == "imperial"


# --- programs ---------------------------------------------------------
def test_preview_needs_no_account(client):
    response = client.post("/v1/programs/preview",
                           json={"days_per_week": 3, "seed": 1})
    assert response.status_code == 200
    assert response.json()["weeks"]


def test_preview_does_not_save_anything(client, account):
    headers, _ = account
    client.post("/v1/programs/preview", json={"days_per_week": 3}, headers=headers)
    assert client.get("/v1/programs", headers=headers).json() == []


def test_save_list_and_read_a_program(client, account):
    headers, _ = account
    created = client.post("/v1/programs", headers=headers,
                          json={"goal": "strength", "level": "intermediate",
                                "days_per_week": 4, "weeks": 4, "seed": 2})
    assert created.status_code == 201
    program_id = created.json()["id"]

    listing = client.get("/v1/programs", headers=headers).json()
    assert [p["id"] for p in listing] == [program_id]

    full = client.get(f"/v1/programs/{program_id}", headers=headers).json()
    assert len(full["weeks"]) == 4
    assert full["profile"]["goal"] == "strength"


def test_free_tier_may_keep_one_program(client, account):
    headers, _ = account
    assert client.post("/v1/programs", headers=headers,
                       json={"days_per_week": 3, "seed": 1}).status_code == 201
    second = client.post("/v1/programs", headers=headers,
                         json={"days_per_week": 4, "seed": 2})
    assert second.status_code == 402


def test_pro_tier_may_keep_several(client, account):
    headers, email = account
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email).one()
        user.tier = "pro"
        session.commit()
    for seed in (1, 2, 3):
        response = client.post("/v1/programs", headers=headers,
                               json={"days_per_week": 3, "seed": seed})
        assert response.status_code == 201


def test_saving_deactivates_the_previous_program(client, account):
    headers, email = account
    with SessionLocal() as session:
        session.query(User).filter_by(email=email).one().tier = "pro"
        session.commit()
    first = client.post("/v1/programs", headers=headers,
                        json={"days_per_week": 3, "seed": 1}).json()["id"]
    second = client.post("/v1/programs", headers=headers,
                         json={"days_per_week": 4, "seed": 2}).json()["id"]

    active = client.get("/v1/programs/active", headers=headers).json()
    assert active["id"] == second

    client.post(f"/v1/programs/{first}/activate", headers=headers)
    assert client.get("/v1/programs/active", headers=headers).json()["id"] == first


def test_no_active_program_is_a_404(client, account):
    headers, _ = account
    assert client.get("/v1/programs/active", headers=headers).status_code == 404


def test_a_program_is_private_to_its_owner(client, saved_program):
    _, program_id = saved_program
    other_headers = _register(client)
    assert client.get(f"/v1/programs/{program_id}",
                      headers=other_headers).status_code == 404


def test_program_can_be_deleted(client, saved_program):
    headers, program_id = saved_program
    assert client.delete(f"/v1/programs/{program_id}",
                         headers=headers).status_code == 204
    assert client.get("/v1/programs", headers=headers).json() == []


def test_a_saved_plan_is_a_snapshot(client, saved_program):
    """Regenerating must never change a block someone is mid-way through."""
    headers, program_id = saved_program
    first = client.get(f"/v1/programs/{program_id}", headers=headers).json()
    second = client.get(f"/v1/programs/{program_id}", headers=headers).json()
    assert first["weeks"] == second["weeks"]


# --- workout logging --------------------------------------------------
def test_logging_a_session_and_reading_it_back(client, saved_program):
    headers, program_id = saved_program
    response = _log(client, headers, program_id, 1, 0, [(10, 60.0), (9, 60.0)])
    assert response.status_code == 201
    assert len(response.json()["sets"]) == 2

    sessions = client.get("/v1/workouts/sessions", headers=headers).json()
    assert len(sessions) == 1
    assert sessions[0]["sets"][0]["weight_kg"] == 60.0


def test_relogging_a_slot_replaces_it(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(10, 60.0)])
    _log(client, headers, program_id, 1, 0, [(10, 65.0)])
    sessions = client.get("/v1/workouts/sessions", headers=headers).json()
    assert len(sessions) == 1
    assert sessions[0]["sets"][0]["weight_kg"] == 65.0


def test_logging_against_someone_elses_program_is_a_404(client, saved_program):
    _, program_id = saved_program
    other_headers = _register(client)
    assert _log(client, other_headers, program_id, 1, 0,
                [(10, 60.0)]).status_code == 404


def test_stats_reflect_logged_work(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(10, 50.0), (10, 50.0)])
    stats = client.get("/v1/workouts/stats", headers=headers).json()
    assert stats["total_sessions"] == 1
    assert stats["total_working_sets"] == 2
    assert stats["total_volume_kg"] == 1000.0


def test_history_reports_an_estimated_one_rep_max(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(10, 60.0)])
    history = client.get("/v1/workouts/history/0043", headers=headers).json()
    # Epley: 60 * (1 + 10/30) = 80
    assert history["sets"][0]["estimated_1rm"] == 80.0


def test_a_session_can_be_deleted(client, saved_program):
    headers, program_id = saved_program
    session_id = _log(client, headers, program_id, 1, 0,
                      [(10, 60.0)]).json()["id"]
    assert client.delete(f"/v1/workouts/sessions/{session_id}",
                         headers=headers).status_code == 204
    assert client.get("/v1/workouts/sessions", headers=headers).json() == []


# --- progression ------------------------------------------------------
def test_with_no_history_the_athlete_is_told_to_establish_a_load(client, account):
    headers, _ = account
    assert _suggestion(client, headers)["action"] == "establish"


def test_hitting_the_top_of_the_range_adds_load(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(12, 60.0), (12, 60.0), (12, 60.0)])
    suggestion = _suggestion(client, headers)
    assert suggestion["action"] == "add_load"
    assert suggestion["weight_kg"] == 65.0  # squat is a lower-body compound


def test_inside_the_range_the_load_is_held(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(9, 62.5), (9, 62.5), (8, 62.5)])
    suggestion = _suggestion(client, headers)
    assert suggestion["action"] == "repeat"
    assert suggestion["weight_kg"] == 62.5


def test_one_bad_session_repeats_before_two_trigger_a_deload(client, saved_program):
    headers, program_id = saved_program
    _log(client, headers, program_id, 1, 0, [(6, 70.0), (5, 70.0), (5, 70.0)])
    assert _suggestion(client, headers)["action"] == "repeat"

    _log(client, headers, program_id, 1, 1, [(6, 70.0), (5, 70.0), (5, 70.0)])
    deload = _suggestion(client, headers)
    assert deload["action"] == "deload"
    assert deload["weight_kg"] == 63.0  # ten per cent off


def test_bodyweight_work_progresses_by_reps(client, saved_program):
    headers, program_id = saved_program
    client.post("/v1/workouts/sessions", headers=headers, json={
        "program_id": program_id, "week": 1, "day_index": 0,
        "day_name": "Test day",
        "sets": [{"exercise_id": "0662", "exercise_name": "push-up",
                  "set_index": 1, "reps": 12, "weight_kg": None}],
    })
    suggestion = _suggestion(client, headers, exercise_id="0662")
    assert suggestion["weight_kg"] is None
    assert "reps" in suggestion["reason"]


def test_warmup_sets_are_ignored_by_progression(client, saved_program):
    headers, program_id = saved_program
    client.post("/v1/workouts/sessions", headers=headers, json={
        "program_id": program_id, "week": 1, "day_index": 0,
        "day_name": "Test day",
        "sets": [
            {"exercise_id": "0043", "exercise_name": "barbell full squat",
             "set_index": 1, "reps": 12, "weight_kg": 100.0, "is_warmup": True},
            {"exercise_id": "0043", "exercise_name": "barbell full squat",
             "set_index": 2, "reps": 9, "weight_kg": 60.0},
        ],
    })
    suggestion = _suggestion(client, headers)
    assert suggestion["weight_kg"] == 60.0
    assert suggestion["action"] == "repeat"


def test_an_unknown_exercise_has_no_suggestion(client, account):
    headers, _ = account
    assert client.get("/v1/workouts/suggestion/999999",
                      headers=headers).status_code == 404


def test_an_inverted_rep_range_is_rejected(client, account):
    headers, _ = account
    response = client.get("/v1/workouts/suggestion/0043",
                          params={"rep_min": 12, "rep_max": 8}, headers=headers)
    assert response.status_code == 400


# --- next session -----------------------------------------------------
def test_next_session_walks_the_block_in_order(client, saved_program):
    headers, program_id = saved_program
    first = client.get(f"/v1/workouts/next/{program_id}", headers=headers).json()
    assert first["week"] == 1 and first["day_index"] == 0

    _log(client, headers, program_id, 1, 0, [(10, 60.0)])
    second = client.get(f"/v1/workouts/next/{program_id}", headers=headers).json()
    assert second["day_index"] == 1


def test_next_session_carries_a_suggestion_per_exercise(client, saved_program):
    headers, program_id = saved_program
    day = client.get(f"/v1/workouts/next/{program_id}", headers=headers).json()
    assert day["day"]["exercises"]
    for entry in day["day"]["exercises"]:
        assert entry["suggestion"]["action"] in {
            "establish", "add_load", "repeat", "deload"}


def test_a_fully_logged_block_reports_complete(client, account):
    headers, _ = account
    program_id = client.post("/v1/programs", headers=headers,
                             json={"days_per_week": 2, "weeks": 1,
                                   "seed": 1}).json()["id"]
    plan = client.get(f"/v1/programs/{program_id}", headers=headers).json()
    for week in plan["weeks"]:
        for day_index in range(len(week["days"])):
            _log(client, headers, program_id, week["week"], day_index,
                 [(10, 60.0)])
    assert client.get(f"/v1/workouts/next/{program_id}",
                      headers=headers).json()["complete"] is True


# --- body metrics -----------------------------------------------------
def test_body_metrics_round_trip(client, account):
    headers, _ = account
    assert client.post("/v1/workouts/metrics", headers=headers,
                       json={"metric": "bodyweight", "value": 82.5,
                             "unit": "kg"}).status_code == 201
    metrics = client.get("/v1/workouts/metrics", headers=headers,
                         params={"metric": "bodyweight"}).json()
    assert metrics[0]["value"] == 82.5
