"""Tests for notification rules, gating and the operator's controls.

The gates are what matters here. Push permission is a one-way door, so a rule
that fires when it should not is not a cosmetic bug — it costs a channel that
cannot be reopened.
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app import notify, scheduler
from app.db import SessionLocal, create_all
from app.models import Notification, NotificationLog, User, utcnow

_emails = (f"notify{n}@example.com" for n in itertools.count())


@pytest.fixture(scope="module")
def client():
    create_all()
    with TestClient(app) as test_client:
        yield test_client


def _account(client) -> tuple[dict, str]:
    email = next(_emails)
    response = client.post("/v1/auth/register",
                           json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def _user(email: str) -> User:
    with SessionLocal() as session:
        return session.query(User).filter_by(email=email.lower()).one()


# --- the registry ------------------------------------------------------
def test_every_category_has_a_master_switch(client):
    body = client.get("/v1/push/preferences",
                      headers=_account(client)[0]).json()
    assert {row["category"] for row in body["categories"]} == set(notify.CATEGORIES)


def test_the_nagging_category_is_off_by_default(client):
    """A nudge nobody asked for costs more than the session it might save."""
    headers, _ = _account(client)
    body = client.get("/v1/push/preferences", headers=headers).json()
    by_key = {row["category"]: row for row in body["categories"]}
    assert by_key[notify.REMINDER_INACTIVITY]["enabled"] is False
    assert by_key[notify.REMINDER_SESSION]["enabled"] is True


def test_a_preference_can_be_turned_on_and_off(client):
    headers, email = _account(client)
    response = client.put("/v1/push/preferences", headers=headers,
                          json={"category": notify.REMINDER_SESSION,
                                "enabled": False})
    assert response.status_code == 200

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        assert notify.user_wants(session, user, notify.REMINDER_SESSION) is False

        notify.set_preference(session, user, notify.REMINDER_SESSION, True)
        assert notify.user_wants(session, user, notify.REMINDER_SESSION) is True


def test_an_unknown_category_is_rejected(client):
    headers, _ = _account(client)
    response = client.put("/v1/push/preferences", headers=headers,
                          json={"category": "not.a.category", "enabled": True})
    assert response.status_code == 400


def test_the_master_switch_overrides_a_personal_preference(client):
    """Turning a category off must stop it for everyone, without a deploy."""
    _, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        notify.set_preference(session, user, notify.REMINDER_SESSION, True)
        assert notify.may_deliver(session, user, notify.REMINDER_SESSION)

        from app.models import NotificationTypeState

        row = session.get(NotificationTypeState, notify.REMINDER_SESSION)
        row.enabled = False
        session.add(row)
        session.commit()

        assert notify.may_deliver(session, user, notify.REMINDER_SESSION) is False

        row.enabled = True
        session.add(row)
        session.commit()


# --- quiet hours -------------------------------------------------------
@pytest.mark.parametrize("hour,expected", [
    (23, True), (2, True), (7, True),   # inside 22:00-08:00
    (8, False), (12, False), (21, False),
])
def test_quiet_hours_wrap_midnight(hour, expected):
    user = User(email="x@example.com", password_hash="x", timezone="UTC",
                quiet_from_hour=22, quiet_to_hour=8)
    moment = datetime(2026, 6, 1, hour, 30, tzinfo=timezone.utc)
    assert notify.in_quiet_hours(user, moment) is expected


def test_quiet_hours_are_read_in_the_users_own_timezone():
    """03:00 in Istanbul is midday in UTC — the zone is the whole point."""
    user = User(email="x@example.com", password_hash="x",
                timezone="Europe/Istanbul", quiet_from_hour=22,
                quiet_to_hour=8)
    # 00:30 UTC is 03:30 in Istanbul: night there, and that is what counts.
    assert notify.in_quiet_hours(
        user, datetime(2026, 6, 1, 0, 30, tzinfo=timezone.utc)) is True
    # 12:00 UTC is 15:00 in Istanbul: awake.
    assert notify.in_quiet_hours(
        user, datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)) is False


def test_an_unusable_timezone_falls_back_rather_than_delivering_anyway():
    user = User(email="x@example.com", password_hash="x",
                timezone="Mars/Olympus", quiet_from_hour=22, quiet_to_hour=8)
    # Falls back to UTC, and the window is still applied.
    assert notify.in_quiet_hours(
        user, datetime(2026, 6, 1, 23, 0, tzinfo=timezone.utc)) is True


def test_an_empty_quiet_window_silences_nothing():
    user = User(email="x@example.com", password_hash="x", timezone="UTC",
                quiet_from_hour=0, quiet_to_hour=0)
    assert notify.in_quiet_hours(
        user, datetime(2026, 6, 1, 3, 0, tzinfo=timezone.utc)) is False


def test_quiet_hours_block_delivery(client):
    _, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        # A window covering the whole day, so the test does not depend on
        # what time it is run.
        user.quiet_from_hour, user.quiet_to_hour = 0, 23
        user.timezone = "UTC"
        session.add(user)
        session.commit()
        assert notify.may_deliver(session, user, notify.REMINDER_SESSION) is False


def test_an_unknown_timezone_is_refused_by_the_api(client):
    headers, _ = _account(client)
    response = client.put("/v1/push/quiet-hours", headers=headers,
                          json={"timezone": "Mars/Olympus"})
    assert response.status_code == 400


def test_quiet_hours_round_trip(client):
    headers, _ = _account(client)
    response = client.put("/v1/push/quiet-hours", headers=headers,
                          json={"timezone": "Europe/Istanbul",
                                "quiet_from_hour": 23, "quiet_to_hour": 7})
    assert response.status_code == 200
    body = client.get("/v1/push/preferences", headers=headers).json()
    assert body["timezone"] == "Europe/Istanbul"
    assert body["quiet_from_hour"] == 23


# --- the daily cap -----------------------------------------------------
def test_the_daily_cap_stops_a_stream(client):
    _, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0  # never quiet
        session.add(user)
        session.commit()
        assert notify.may_deliver(session, user, notify.REMINDER_SESSION)

        for _ in range(notify.DAILY_CAP):
            session.add(NotificationLog(user_id=user.id,
                                        category=notify.REMINDER_SESSION))
        session.commit()

        assert notify.may_deliver(session, user, notify.REMINDER_SESSION) is False


def test_an_announcement_is_not_held_back_by_the_cap(client):
    """Rare and deliberate; the cap exists to bound automatic rules."""
    _, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        for _ in range(notify.DAILY_CAP + 2):
            session.add(NotificationLog(user_id=user.id,
                                        category=notify.REMINDER_SESSION))
        session.commit()

        assert notify.may_deliver(session, user, notify.REMINDER_SESSION) is False
        assert notify.may_deliver(session, user, notify.ANNOUNCEMENT) is True


def test_yesterdays_notifications_do_not_count(client):
    _, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        for _ in range(notify.DAILY_CAP + 1):
            session.add(NotificationLog(
                user_id=user.id, category=notify.REMINDER_SESSION,
                sent_at=utcnow() - timedelta(days=2)))
        session.commit()
        assert notify.may_deliver(session, user, notify.REMINDER_SESSION) is True


# --- the scheduler rules ----------------------------------------------
def _program_and_sessions(client, headers, weeks=1, days=2, log_all=False):
    program_id = client.post("/v1/programs", headers=headers,
                             json={"level": "beginner", "days_per_week": days,
                                   "weeks": weeks, "seed": 1}).json()["id"]
    plan = client.get(f"/v1/programs/{program_id}", headers=headers).json()
    if log_all:
        for week in plan["weeks"]:
            for day_index in range(len(week["days"])):
                client.post("/v1/workouts/sessions", headers=headers, json={
                    "program_id": program_id, "week": week["week"],
                    "day_index": day_index, "day_name": "Day",
                    "sets": [{"exercise_id": "0043", "exercise_name": "squat",
                              "set_index": 1, "reps": 10, "weight_kg": 60.0}],
                })
    return program_id


def test_block_complete_fires_once_when_every_day_is_logged(client):
    headers, email = _account(client)
    _program_and_sessions(client, headers, weeks=1, days=2, log_all=True)

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        session.commit()

        assert scheduler.block_complete(session, user, utcnow()) is True
        # Idempotent: a tick that runs again must not send it twice.
        assert scheduler.block_complete(session, user, utcnow()) is False

        count = session.query(Notification).filter_by(
            user_id=user.id, kind=notify.REMINDER_BLOCK_COMPLETE).count()
        assert count == 1


def test_block_complete_does_not_fire_mid_block(client):
    headers, email = _account(client)
    _program_and_sessions(client, headers, weeks=1, days=2, log_all=False)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        assert scheduler.block_complete(session, user, utcnow()) is False


def test_the_session_reminder_only_fires_at_the_chosen_local_hour(client):
    headers, email = _account(client)
    _program_and_sessions(client, headers, weeks=1, days=2, log_all=False)

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.timezone = "UTC"
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        session.commit()

        wrong_hour = datetime(2026, 6, 1, 4, 0, tzinfo=timezone.utc)
        assert scheduler.session_reminder(session, user, wrong_hour) is False

        right_hour = datetime(2026, 6, 1, scheduler.DEFAULT_REMINDER_HOUR, 0,
                              tzinfo=timezone.utc)
        assert scheduler.session_reminder(session, user, right_hour) is True


def test_no_session_reminder_without_an_active_program(client):
    headers, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        session.commit()
        moment = datetime(2026, 6, 1, scheduler.DEFAULT_REMINDER_HOUR, 0,
                          tzinfo=timezone.utc)
        assert scheduler.session_reminder(session, user, moment) is False


def test_the_inactivity_nudge_needs_a_history_to_be_quiet_from(client):
    """Someone who never trained is not inactive; they are new."""
    headers, email = _account(client)
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.quiet_from_hour = user.quiet_to_hour = 0
        session.add(user)
        session.commit()
        moment = datetime(2026, 6, 1, scheduler.DEFAULT_REMINDER_HOUR, 0,
                          tzinfo=timezone.utc)
        assert scheduler.inactivity_nudge(session, user, moment) is False


def test_a_tick_runs_without_error_and_reports_counts(client):
    _account(client)
    with SessionLocal() as session:
        counts = scheduler.tick(session)
    assert set(counts) == {rule.__name__ for rule in scheduler.RULES}


# --- the admin surface -------------------------------------------------
def _make_admin(email: str) -> None:
    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        user.is_admin = True
        session.add(user)
        session.commit()


def test_the_admin_surface_is_invisible_to_everyone_else(client):
    """404 rather than 403: it does not announce its own existence."""
    headers, _ = _account(client)
    assert client.get("/v1/admin/overview", headers=headers).status_code == 404
    assert client.get("/v1/admin/notification-types",
                      headers=headers).status_code == 404
    assert client.post("/v1/admin/announcements", headers=headers,
                       json={"title": "x", "body": "y"}).status_code == 404


def test_the_admin_surface_needs_an_account_at_all(client):
    assert client.get("/v1/admin/overview").status_code == 401


def test_an_admin_can_read_the_overview(client):
    headers, email = _account(client)
    _make_admin(email)
    body = client.get("/v1/admin/overview", headers=headers).json()
    assert "push_configured" in body
    assert body["users"] >= 1


def test_an_admin_can_switch_a_category_off_and_on(client):
    headers, email = _account(client)
    _make_admin(email)

    response = client.put(
        f"/v1/admin/notification-types/{notify.REMINDER_DELOAD}",
        params={"enabled": False}, headers=headers)
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    types = client.get("/v1/admin/notification-types", headers=headers).json()
    by_key = {row["category"]: row for row in types}
    assert by_key[notify.REMINDER_DELOAD]["enabled"] is False

    client.put(f"/v1/admin/notification-types/{notify.REMINDER_DELOAD}",
               params={"enabled": True}, headers=headers)


def test_switching_an_unknown_category_is_a_404(client):
    headers, email = _account(client)
    _make_admin(email)
    assert client.put("/v1/admin/notification-types/nope",
                      params={"enabled": False}, headers=headers).status_code == 404


def test_an_announcement_defaults_to_the_author_alone(client):
    """A message to everyone cannot be recalled, so 'self' is the default."""
    headers, email = _account(client)
    _make_admin(email)
    body = client.post("/v1/admin/announcements", headers=headers,
                       json={"title": "Hello", "body": "Testing"}).json()
    assert body["audience"] == "self"
    assert body["sent_at"] is not None

    # The in-app record reaches the author, whether or not push is configured.
    notifications = client.get("/v1/notifications", headers=headers).json()
    assert any(n["kind"] == notify.ANNOUNCEMENT for n in notifications)


def test_an_announcement_to_everyone_records_for_everyone(client):
    headers, email = _account(client)
    _make_admin(email)
    other_headers, _ = _account(client)

    client.post("/v1/admin/announcements", headers=headers,
                json={"title": "News", "body": "Something happened",
                      "audience": "all"})

    theirs = client.get("/v1/notifications", headers=other_headers).json()
    assert any(n["kind"] == notify.ANNOUNCEMENT for n in theirs)


def test_an_announcement_skips_people_who_turned_them_off(client):
    headers, email = _account(client)
    _make_admin(email)
    other_headers, _ = _account(client)
    client.put("/v1/push/preferences", headers=other_headers,
               json={"category": notify.ANNOUNCEMENT, "enabled": False})

    client.post("/v1/admin/announcements", headers=headers,
                json={"title": "Unwanted", "body": "Should not arrive",
                      "audience": "all"})

    theirs = client.get("/v1/notifications", headers=other_headers).json()
    assert not any(n["kind"] == notify.ANNOUNCEMENT for n in theirs)


def test_announcements_are_listed_for_the_author(client):
    headers, email = _account(client)
    _make_admin(email)
    client.post("/v1/admin/announcements", headers=headers,
                json={"title": "Listed", "body": "Body"})
    listed = client.get("/v1/admin/announcements", headers=headers).json()
    assert any(row["title"] == "Listed" for row in listed)


# --- push configuration -----------------------------------------------
def test_push_config_reports_whether_it_is_usable(client):
    body = client.get("/v1/push/config").json()
    assert body["enabled"] is False  # no VAPID keys in the test environment
    assert body["public_key"] is None


def test_a_test_send_without_keys_is_a_clear_503(client):
    headers, _ = _account(client)
    response = client.post("/v1/push/test", headers=headers)
    assert response.status_code == 503


def test_subscribing_twice_from_one_browser_keeps_one_row(client):
    headers, email = _account(client)
    subscription = {
        "endpoint": "https://push.example.com/abc123",
        "keys": {"p256dh": "key-material", "auth": "auth-secret"},
    }
    assert client.post("/v1/push/subscriptions", json=subscription,
                       headers=headers).status_code == 204
    assert client.post("/v1/push/subscriptions", json=subscription,
                       headers=headers).status_code == 204

    from app.models import PushSubscription

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        rows = session.query(PushSubscription).filter_by(user_id=user.id).all()
    assert len(rows) == 1


def test_a_subscription_can_be_removed(client):
    headers, email = _account(client)
    subscription = {
        "endpoint": "https://push.example.com/removable",
        "keys": {"p256dh": "key-material", "auth": "auth-secret"},
    }
    client.post("/v1/push/subscriptions", json=subscription, headers=headers)
    assert client.request("DELETE", "/v1/push/subscriptions",
                          json=subscription, headers=headers).status_code == 204

    from app.models import PushSubscription

    with SessionLocal() as session:
        user = session.query(User).filter_by(email=email.lower()).one()
        rows = session.query(PushSubscription).filter_by(user_id=user.id).all()
    assert rows == []


def test_a_device_moving_to_another_account_stops_serving_the_first(client):
    """A shared phone must not keep delivering to whoever had it before."""
    first_headers, first_email = _account(client)
    second_headers, second_email = _account(client)
    subscription = {
        "endpoint": "https://push.example.com/shared-device",
        "keys": {"p256dh": "key-material", "auth": "auth-secret"},
    }
    client.post("/v1/push/subscriptions", json=subscription, headers=first_headers)
    client.post("/v1/push/subscriptions", json=subscription, headers=second_headers)

    from app.models import PushSubscription

    with SessionLocal() as session:
        first = session.query(User).filter_by(email=first_email.lower()).one()
        second = session.query(User).filter_by(email=second_email.lower()).one()
        assert session.query(PushSubscription).filter_by(
            user_id=first.id).count() == 0
        assert session.query(PushSubscription).filter_by(
            user_id=second.id).count() == 1


def test_push_endpoints_need_an_account(client):
    assert client.get("/v1/push/preferences").status_code == 401
    assert client.post("/v1/push/subscriptions", json={
        "endpoint": "https://x", "keys": {"p256dh": "a", "auth": "b"},
    }).status_code == 401
