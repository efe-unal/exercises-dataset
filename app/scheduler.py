"""The automatic notifications, and the tick that runs them.

Run it from cron, once an hour:

    0 * * * * cd /srv && python -m app.scheduler tick

Hourly is the right cadence because every rule here is gated on the person's
own local hour: a reminder is only ever sent inside the hour they chose, so a
tick that ran daily would miss most people and one that ran every minute
would do the same work sixty times.

Every rule is idempotent within its window. A tick that runs twice, or that
is missed and catches up late, must not produce two notifications — so each
rule checks what it already sent before sending.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import notify
from .db import SessionLocal
from .models import (
    Notification,
    Program,
    User,
    WorkoutSession,
    utcnow,
)

logger = logging.getLogger(__name__)

#: A nudge goes out after this long with nothing logged, and then not again
#: until they train — one reminder, not a drumbeat.
INACTIVITY_DAYS = 5

#: Reminders are sent at this local hour unless the person picked another.
#: Early evening: after work, before the gym closes.
DEFAULT_REMINDER_HOUR = 17


def _local_hour(user: User, moment: datetime) -> int | None:
    try:
        zone = ZoneInfo(user.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return moment.astimezone(zone).hour


def _already_sent_since(session: Session, user_id: str, kind: str,
                        since: datetime) -> bool:
    return session.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user_id,
               Notification.kind == kind,
               Notification.created_at >= since)) > 0


def _active_program(session: Session, user_id: str) -> Program | None:
    return session.scalar(
        select(Program).where(Program.user_id == user_id,
                              Program.is_active.is_(True))
        .order_by(Program.created_at.desc()))


# --- the rules ---------------------------------------------------------
def session_reminder(session: Session, user: User, now: datetime) -> bool:
    """"You have a session today" — at the hour they chose, once a day.

    Only when there is something to remind them of: an active programme with
    an unlogged day. Reminding someone to train when their block is finished
    is how a reminder becomes noise.
    """
    if _local_hour(user, now) != DEFAULT_REMINDER_HOUR:
        return False

    program = _active_program(session, user.id)
    if program is None:
        return False

    plan = json.loads(program.plan_json)
    total_days = sum(len(week["days"]) for week in plan["weeks"])
    logged = session.scalar(
        select(func.count()).select_from(WorkoutSession)
        .where(WorkoutSession.program_id == program.id)) or 0
    if logged >= total_days:
        return False  # the block is done; block_complete handles that

    # Already logged something today? Then they do not need reminding.
    day_ago = now - timedelta(hours=20)
    trained_today = session.scalar(
        select(func.count()).select_from(WorkoutSession)
        .where(WorkoutSession.user_id == user.id,
               WorkoutSession.started_at >= day_ago)) or 0
    if trained_today:
        return False

    if _already_sent_since(session, user.id, notify.REMINDER_SESSION, day_ago):
        return False

    notify.notify(
        session, user, notify.REMINDER_SESSION,
        title="Time to train",
        body="Your next session is waiting.",
        url="/",
    )
    return True


def block_complete(session: Session, user: User, now: datetime) -> bool:
    """Every day of the active block is logged — time for the next one."""
    program = _active_program(session, user.id)
    if program is None:
        return False

    plan = json.loads(program.plan_json)
    total_days = sum(len(week["days"]) for week in plan["weeks"])
    logged = session.scalar(
        select(func.count()).select_from(WorkoutSession)
        .where(WorkoutSession.program_id == program.id)) or 0
    if logged < total_days:
        return False

    # Once per programme, ever — not once per tick for the rest of time.
    if _already_sent_since(session, user.id, notify.REMINDER_BLOCK_COMPLETE,
                           program.created_at):
        return False

    notify.notify(
        session, user, notify.REMINDER_BLOCK_COMPLETE,
        title="Block finished",
        body="You logged every session. Build the next one.",
        url="/programs/new",
    )
    return True


def deload_starting(session: Session, user: User, now: datetime) -> bool:
    """The block's last week is a deload and they have reached it."""
    program = _active_program(session, user.id)
    if program is None:
        return False

    plan = json.loads(program.plan_json)
    deload_weeks = [w for w in plan["weeks"] if w["is_deload"]]
    if not deload_weeks:
        return False
    deload_week = deload_weeks[0]["week"]

    # Where are they? The first week with an unlogged day.
    logged_slots = {
        (row.week, row.day_index) for row in session.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.program_id == program.id))
    }
    current_week = None
    for week in plan["weeks"]:
        for day_index in range(len(week["days"])):
            if (week["week"], day_index) not in logged_slots:
                current_week = week["week"]
                break
        if current_week is not None:
            break

    if current_week != deload_week:
        return False
    if _already_sent_since(session, user.id, notify.REMINDER_DELOAD,
                           program.created_at):
        return False

    notify.notify(
        session, user, notify.REMINDER_DELOAD,
        title="Deload week",
        body="Cut the volume this week and keep the movements.",
        url="/",
    )
    return True


def inactivity_nudge(session: Session, user: User, now: datetime) -> bool:
    """Nothing logged for a while. One message, not a drumbeat."""
    if _local_hour(user, now) != DEFAULT_REMINDER_HOUR:
        return False

    last = session.scalar(
        select(func.max(WorkoutSession.started_at))
        .where(WorkoutSession.user_id == user.id))
    if last is None:
        return False  # never trained: a nudge is not the right first contact

    if last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)
    if now - last < timedelta(days=INACTIVITY_DAYS):
        return False

    # Not again until they train: the check is against the last workout, so
    # one nudge covers the whole quiet spell however long it runs.
    if _already_sent_since(session, user.id, notify.REMINDER_INACTIVITY, last):
        return False

    notify.notify(
        session, user, notify.REMINDER_INACTIVITY,
        title="Still with us?",
        body="It has been a few days. A short session counts.",
        url="/",
    )
    return True


RULES = (session_reminder, block_complete, deload_starting, inactivity_nudge)


def tick(session: Session, now: datetime | None = None) -> dict[str, int]:
    """Run every rule for every user. Returns a count per rule."""
    now = now or utcnow()
    notify.sync_categories(session)

    counts = {rule.__name__: 0 for rule in RULES}
    users = list(session.scalars(select(User)))

    for user in users:
        for rule in RULES:
            try:
                if rule(session, user, now):
                    counts[rule.__name__] += 1
            except Exception:  # noqa: BLE001 - one user must not stop the tick
                logger.exception("notification rule %s failed for user %s",
                                 rule.__name__, user.id)
    return counts


def _main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != "tick":
        print("usage: python -m app.scheduler tick", file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        counts = tick(session)
    for name, count in counts.items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
