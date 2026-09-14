"""Tests for the social layer.

The privacy tests are the important ones: the failure mode that matters here
is one person's workout becoming visible to someone they never showed it to.
"""

import itertools

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.social import RESERVED_USERNAMES, validate_username, UsernameError

_emails = (f"social{n}@example.com" for n in itertools.count())


@pytest.fixture(scope="module")
def client():
    from app.db import create_all

    create_all()
    with TestClient(app) as test_client:
        yield test_client


def _account(client, username: str | None = None) -> dict:
    """Register an account, optionally claiming a handle."""
    response = client.post("/v1/auth/register",
                           json={"email": next(_emails),
                                 "password": "correct-horse-1"})
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    if username:
        assert client.patch("/v1/auth/me", json={"username": username},
                            headers=headers).status_code == 200
    return headers


def _logged_session(client, headers, day="Full body A") -> str:
    program_id = client.post("/v1/programs", headers=headers,
                             json={"level": "beginner", "days_per_week": 3,
                                   "weeks": 4, "seed": 1}).json()["id"]
    return client.post("/v1/workouts/sessions", headers=headers, json={
        "program_id": program_id, "week": 1, "day_index": 0, "day_name": day,
        "sets": [{"exercise_id": "0043", "exercise_name": "barbell full squat",
                  "set_index": i + 1, "reps": 10, "weight_kg": 60.0}
                 for i in range(3)],
    }).json()["id"]


# --- usernames --------------------------------------------------------
@pytest.mark.parametrize("username", ["ab", "a" * 31, "_leading", "has space",
                                      "has-dash", "üniko", ""])
def test_invalid_usernames_are_refused(username):
    with pytest.raises(UsernameError):
        validate_username(username)


@pytest.mark.parametrize("username", ["ayse", "ayse_lifts", "a1b2c3", "x" * 30])
def test_valid_usernames_are_accepted(username):
    assert validate_username(username) == username.lower()


def test_reserved_usernames_are_refused():
    for reserved in list(RESERVED_USERNAMES)[:5]:
        with pytest.raises(UsernameError):
            validate_username(reserved)


def test_usernames_are_case_insensitive_but_display_is_kept(client):
    headers = _account(client)
    body = client.patch("/v1/auth/me", json={"username": "AyseLifts"},
                        headers=headers).json()
    assert body["username"] == "ayselifts"
    assert client.get("/v1/profiles/AYSELIFTS").status_code == 200


def test_a_taken_username_is_refused(client):
    _account(client, "takenhandle")
    other = _account(client)
    assert client.patch("/v1/auth/me", json={"username": "TakenHandle"},
                        headers=other).status_code == 409


def test_a_reserved_username_is_refused_over_http(client):
    headers = _account(client)
    assert client.patch("/v1/auth/me", json={"username": "admin"},
                        headers=headers).status_code == 422


def test_an_unknown_profile_is_a_404(client):
    assert client.get("/v1/profiles/nobodyhere").status_code == 404


# --- publishing and privacy -------------------------------------------
def test_a_logged_session_is_private_until_published(client):
    headers = _account(client, "privateone")
    _logged_session(client, headers)
    assert client.get("/v1/profiles/privateone").json()["sessions"] == []


def test_publishing_puts_a_session_on_the_profile(client):
    headers = _account(client, "publisher1")
    session_id = _logged_session(client, headers)
    published = client.post(f"/v1/workouts/sessions/{session_id}/publish",
                            json={"caption": "Good day"}, headers=headers)
    assert published.status_code == 200
    assert published.json()["total_sets"] == 3
    assert published.json()["total_volume_kg"] == 1800.0

    profile = client.get("/v1/profiles/publisher1").json()
    assert len(profile["sessions"]) == 1
    assert profile["sessions"][0]["caption"] == "Good day"


def test_unpublishing_takes_it_back_off(client):
    headers = _account(client, "publisher2")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    assert client.delete(f"/v1/workouts/sessions/{session_id}/publish",
                         headers=headers).status_code == 204
    assert client.get("/v1/profiles/publisher2").json()["sessions"] == []


def test_an_unpublished_session_is_a_404_by_direct_link(client):
    """The same answer as 'never existed' — a 403 would confirm it exists."""
    headers = _account(client, "publisher3")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    assert client.get(
        f"/v1/profiles/publisher3/sessions/{session_id}").status_code == 200

    client.delete(f"/v1/workouts/sessions/{session_id}/publish", headers=headers)
    assert client.get(
        f"/v1/profiles/publisher3/sessions/{session_id}").status_code == 404


def test_publishing_someone_elses_session_is_a_404(client):
    owner = _account(client, "owner1")
    session_id = _logged_session(client, owner)
    stranger = _account(client, "stranger1")
    assert client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                       headers=stranger).status_code == 404


def test_publishing_needs_a_username_first(client):
    headers = _account(client)  # no handle claimed
    session_id = _logged_session(client, headers)
    assert client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                       headers=headers).status_code == 409


def test_a_profile_never_carries_an_email(client):
    headers = _account(client, "noemailhere")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    body = client.get("/v1/profiles/noemailhere").text
    assert "@example.com" not in body


def test_a_profile_never_carries_the_program_or_owner_id(client):
    """A published session is trimmed, not dumped from the row."""
    headers = _account(client, "trimmed1")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    published = client.get("/v1/profiles/trimmed1").json()["sessions"][0]
    assert "user_id" not in published
    assert "program_id" not in published


def test_a_signed_out_visitor_can_read_a_profile(client):
    """A shared card has to lead somewhere for someone without the app."""
    headers = _account(client, "publicface")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    body = client.get("/v1/profiles/publicface").json()
    assert len(body["sessions"]) == 1
    assert body["is_self"] is False
    assert body["is_following"] is False


def test_a_bad_token_reads_as_signed_out_on_a_public_profile(client):
    headers = _account(client, "publicface2")
    session_id = _logged_session(client, headers)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=headers)
    response = client.get("/v1/profiles/publicface2",
                          headers={"Authorization": "Bearer nonsense"})
    assert response.status_code == 200
    assert response.json()["is_self"] is False


def test_the_owner_sees_the_profile_as_their_own(client):
    headers = _account(client, "selfview")
    assert client.get("/v1/profiles/selfview",
                      headers=headers).json()["is_self"] is True


# --- following --------------------------------------------------------
def test_follow_and_unfollow(client):
    followee = _account(client, "followee1")
    follower = _account(client, "follower1")

    assert client.post("/v1/profiles/followee1/follow",
                       headers=follower).status_code == 204
    assert client.get("/v1/profiles/followee1",
                      headers=follower).json()["is_following"] is True
    assert client.get("/v1/profiles/followee1").json()["profile"]["followers"] == 1

    assert client.delete("/v1/profiles/followee1/follow",
                         headers=follower).status_code == 204
    assert client.get("/v1/profiles/followee1",
                      headers=follower).json()["is_following"] is False
    assert followee  # the fixture account is what makes the profile exist


def test_following_twice_is_the_same_as_once(client):
    _account(client, "followee2")
    follower = _account(client, "follower2")
    client.post("/v1/profiles/followee2/follow", headers=follower)
    client.post("/v1/profiles/followee2/follow", headers=follower)
    assert client.get("/v1/profiles/followee2").json()["profile"]["followers"] == 1


def test_you_cannot_follow_yourself(client):
    headers = _account(client, "loner1")
    assert client.post("/v1/profiles/loner1/follow",
                       headers=headers).status_code == 400


def test_following_grants_no_access_to_private_sessions(client):
    """The rule the whole module exists to enforce."""
    owner = _account(client, "guarded1")
    _logged_session(client, owner)  # logged, never published
    follower = _account(client, "follower3")
    client.post("/v1/profiles/guarded1/follow", headers=follower)

    assert client.get("/v1/profiles/guarded1",
                      headers=follower).json()["sessions"] == []
    assert client.get("/v1/workouts/sessions",
                      headers=follower).json() == []


def test_following_lists(client):
    _account(client, "followee3")
    follower = _account(client, "follower4")
    client.post("/v1/profiles/followee3/follow", headers=follower)

    following = client.get("/v1/me/following", headers=follower).json()
    assert [entry["username"] for entry in following] == ["followee3"]


# --- notifications ----------------------------------------------------
def test_publishing_notifies_followers(client):
    author = _account(client, "author1")
    follower = _account(client, "reader1")
    client.post("/v1/profiles/author1/follow", headers=follower)

    session_id = _logged_session(client, author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=author)

    notifications = client.get("/v1/notifications", headers=follower).json()
    assert len(notifications) == 1
    assert notifications[0]["kind"] == "social.workout_published"
    assert notifications[0]["actor_username"] == "author1"
    assert notifications[0]["session_id"] == session_id
    assert client.get("/v1/notifications/unread-count",
                      headers=follower).json()["unread"] == 1


def test_a_non_follower_is_not_notified(client):
    author = _account(client, "author2")
    stranger = _account(client, "stranger2")
    session_id = _logged_session(client, author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=author)
    assert client.get("/v1/notifications", headers=stranger).json() == []


def test_editing_a_caption_does_not_notify_again(client):
    author = _account(client, "author3")
    follower = _account(client, "reader3")
    client.post("/v1/profiles/author3/follow", headers=follower)

    session_id = _logged_session(client, author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish",
                json={"caption": "first"}, headers=author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish",
                json={"caption": "second"}, headers=author)

    assert len(client.get("/v1/notifications", headers=follower).json()) == 1


def test_notifications_can_be_marked_read(client):
    author = _account(client, "author4")
    follower = _account(client, "reader4")
    client.post("/v1/profiles/author4/follow", headers=follower)
    session_id = _logged_session(client, author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=author)

    assert client.post("/v1/notifications/read",
                       headers=follower).status_code == 204
    assert client.get("/v1/notifications/unread-count",
                      headers=follower).json()["unread"] == 0
    assert client.get("/v1/notifications", headers=follower,
                      params={"unread_only": True}).json() == []


def test_notifications_are_private_to_their_recipient(client):
    author = _account(client, "author5")
    follower = _account(client, "reader5")
    outsider = _account(client, "outsider5")
    client.post("/v1/profiles/author5/follow", headers=follower)
    session_id = _logged_session(client, author)
    client.post(f"/v1/workouts/sessions/{session_id}/publish", json={},
                headers=author)

    assert client.get("/v1/notifications", headers=outsider).json() == []


@pytest.mark.parametrize("path", [
    "/v1/me/following",
    "/v1/me/followers",
    "/v1/notifications",
    "/v1/notifications/unread-count",
])
def test_private_social_endpoints_need_an_account(client, path):
    assert client.get(path).status_code == 401
