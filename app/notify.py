"""The notification registry and the rules that decide whether to deliver.

Push permission is a one-way door. Once someone turns notifications off in
their phone's settings, no product decision can get them back — so every
notification spends a little of a budget that cannot be topped up. Everything
here exists to spend it carefully:

* **Categories, not one switch.** Someone annoyed by announcements must be
  able to silence those alone; if the only control were all-or-nothing they
  would silence the useful ones too, and never return.
* **A master switch per category.** The operator can turn one off for
  everyone without a deploy, which is what makes a noisy rule a mistake that
  can be undone rather than one shipped to every phone.
* **Quiet hours in the person's own timezone.** A reminder at 03:00 gets the
  app deleted.
* **A daily cap.** No combination of rules can produce a stream.

Adding a category is one entry in ``CATEGORIES`` — no migration, because a
missing preference row means "use this category's default".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import push
from .models import (
    Notification,
    NotificationLog,
    NotificationSetting,
    NotificationTypeState,
    PushSubscription,
    User,
    utcnow,
)

logger = logging.getLogger(__name__)

#: No one receives more than this many notifications in a rolling day,
#: whatever rules fire. Announcements are exempt — see :func:`deliver`.
DAILY_CAP = 4


@dataclass(frozen=True)
class Category:
    """One kind of notification, and how it behaves by default."""

    key: str
    #: Shown in settings. Clients translate by key and fall back to this.
    label: str
    #: Whether someone who has never touched the setting receives it.
    default_enabled: bool
    #: Whether quiet hours apply. Nothing is exempt today, but a genuinely
    #: urgent category later would be.
    respects_quiet_hours: bool = True
    #: Whether the daily cap applies.
    respects_cap: bool = True


SOCIAL_WORKOUT_PUBLISHED = "social.workout_published"
REMINDER_SESSION = "reminder.session"
REMINDER_BLOCK_COMPLETE = "reminder.block_complete"
REMINDER_INACTIVITY = "reminder.inactivity"
REMINDER_DELOAD = "reminder.deload"
ANNOUNCEMENT = "announcement"

CATEGORIES: dict[str, Category] = {
    SOCIAL_WORKOUT_PUBLISHED: Category(
        SOCIAL_WORKOUT_PUBLISHED,
        "Someone you follow published a workout",
        default_enabled=True,
    ),
    REMINDER_SESSION: Category(
        REMINDER_SESSION,
        "Training reminder",
        default_enabled=True,
    ),
    REMINDER_BLOCK_COMPLETE: Category(
        REMINDER_BLOCK_COMPLETE,
        "Your programme is finished",
        default_enabled=True,
    ),
    REMINDER_INACTIVITY: Category(
        REMINDER_INACTIVITY,
        "A nudge after a quiet spell",
        # Off unless asked for. This is the one that reads as nagging, and a
        # nudge nobody wanted costs more than the session it might recover.
        default_enabled=False,
    ),
    REMINDER_DELOAD: Category(
        REMINDER_DELOAD,
        "Deload week starting",
        default_enabled=True,
    ),
    ANNOUNCEMENT: Category(
        ANNOUNCEMENT,
        "News about the app",
        default_enabled=True,
        # An announcement is rare and deliberate, so it is not held back by
        # a cap meant to bound automatic rules. Quiet hours still apply.
        respects_cap=False,
    ),
}


def sync_categories(session: Session) -> None:
    """Make sure every category in code has a master switch row.

    Called at startup. A new category arrives switched on; one removed from
    code keeps its row, harmlessly, rather than losing the operator's choice
    if it comes back.
    """
    known = {row.category for row in session.scalars(select(NotificationTypeState))}
    missing = [key for key in CATEGORIES if key not in known]
    if not missing:
        return
    session.add_all([NotificationTypeState(category=key) for key in missing])
    session.commit()


def category_enabled_globally(session: Session, key: str) -> bool:
    row = session.get(NotificationTypeState, key)
    # An unseeded category is treated as on: the master switch exists to turn
    # things off, and a missing row must not silently disable a feature.
    return True if row is None else row.enabled


def user_wants(session: Session, user: User, key: str) -> bool:
    """Whether this person receives this category."""
    category = CATEGORIES.get(key)
    if category is None:
        return False
    setting = session.scalar(
        select(NotificationSetting).where(
            NotificationSetting.user_id == user.id,
            NotificationSetting.category == key))
    return category.default_enabled if setting is None else setting.enabled


def set_preference(session: Session, user: User, key: str,
                   enabled: bool) -> None:
    if key not in CATEGORIES:
        raise ValueError(f"unknown notification category: {key}")
    setting = session.scalar(
        select(NotificationSetting).where(
            NotificationSetting.user_id == user.id,
            NotificationSetting.category == key))
    if setting is None:
        session.add(NotificationSetting(user_id=user.id, category=key,
                                        enabled=enabled))
    else:
        setting.enabled = enabled
        setting.updated_at = utcnow()
        session.add(setting)
    session.commit()


def preferences_for(session: Session, user: User) -> list[dict]:
    """Every category with this person's answer — what a settings page reads."""
    chosen = {
        row.category: row.enabled
        for row in session.scalars(
            select(NotificationSetting)
            .where(NotificationSetting.user_id == user.id))
    }
    return [
        {
            "category": category.key,
            "label": category.label,
            "enabled": chosen.get(category.key, category.default_enabled),
            "available": category_enabled_globally(session, category.key),
        }
        for category in CATEGORIES.values()
    ]


def _zone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        # A bad zone must not mean "deliver anyway at whatever hour" — UTC is
        # at least a defined answer that quiet hours can be applied against.
        logger.warning("user %s has an unusable timezone %r; using UTC",
                       user.id, user.timezone)
        return ZoneInfo("UTC")


def in_quiet_hours(user: User, moment: datetime | None = None) -> bool:
    """Whether it is currently night for this person."""
    local = (moment or utcnow()).astimezone(_zone(user))
    start, end = user.quiet_from_hour, user.quiet_to_hour
    if start == end:
        return False  # an empty window, not a whole silent day
    if start < end:
        return start <= local.hour < end
    # The window wraps midnight, which is the normal case: 22:00 to 08:00.
    return local.hour >= start or local.hour < end


def sent_today(session: Session, user_id: str) -> int:
    since = utcnow() - timedelta(days=1)
    return session.scalar(
        select(func.count()).select_from(NotificationLog)
        .where(NotificationLog.user_id == user_id,
               NotificationLog.sent_at >= since)) or 0


def may_deliver(session: Session, user: User, key: str) -> bool:
    """Every gate between a rule firing and a phone buzzing."""
    category = CATEGORIES.get(key)
    if category is None:
        return False
    if not category_enabled_globally(session, key):
        return False
    if not user_wants(session, user, key):
        return False
    if category.respects_quiet_hours and in_quiet_hours(user):
        return False
    if category.respects_cap and sent_today(session, user.id) >= DAILY_CAP:
        return False
    return True


def record(session: Session, user_id: str, key: str,
           actor_id: str | None = None,
           session_id: str | None = None) -> Notification:
    """Store the in-app notification, independent of any push delivery.

    The list in the app is the source of truth. Push is a courtesy on top: it
    can be unconfigured, refused, or lost, and the notification still exists.
    """
    notification = Notification(user_id=user_id, kind=key, actor_id=actor_id,
                                session_id=session_id)
    session.add(notification)
    session.commit()
    return notification


def deliver(session: Session, user: User, key: str, title: str, body: str,
            url: str = "/", *, force: bool = False) -> bool:
    """Push one notification to every device this person has registered.

    Returns whether anything was sent. ``force`` skips the preference and
    quiet-hour gates and exists for one case only: a test send the operator
    addressed to themselves.
    """
    if not push.is_configured():
        return False
    if not force and not may_deliver(session, user, key):
        return False

    subscriptions = list(session.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user.id)))
    if not subscriptions:
        return False

    payload = {"title": title, "body": body, "url": url, "category": key}
    delivered = False

    for subscription in subscriptions:
        try:
            push.send(subscription.endpoint, subscription.p256dh,
                      subscription.auth, payload)
        except push.PushGone:
            # The browser threw the subscription away; so do we, or it is
            # retried forever.
            session.delete(subscription)
            continue
        except Exception:  # noqa: BLE001 - one dead device must not stop the rest
            subscription.consecutive_failures += 1
            if subscription.consecutive_failures >= push.MAX_CONSECUTIVE_FAILURES:
                logger.info("dropping subscription %s after repeated failures",
                            subscription.id)
                session.delete(subscription)
            else:
                session.add(subscription)
            logger.warning("push delivery failed for subscription %s",
                           subscription.id, exc_info=True)
            continue

        subscription.consecutive_failures = 0
        subscription.last_success_at = utcnow()
        session.add(subscription)
        delivered = True

    if delivered:
        session.add(NotificationLog(user_id=user.id, category=key))
    session.commit()
    return delivered


def notify(session: Session, user: User, key: str, title: str, body: str,
           url: str = "/", actor_id: str | None = None,
           session_id: str | None = None) -> None:
    """Record a notification and try to push it.

    The one entry point rules should call: it keeps the in-app list and the
    push in step, and applies every gate in one place.
    """
    if not category_enabled_globally(session, key):
        return
    if not user_wants(session, user, key):
        return
    record(session, user.id, key, actor_id=actor_id, session_id=session_id)
    deliver(session, user, key, title, body, url)


def utc_now() -> datetime:
    """Re-exported so callers need not import two modules for one clock."""
    return datetime.now(timezone.utc)
