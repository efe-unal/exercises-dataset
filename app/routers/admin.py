"""The operator's controls: announcements, and the master switches.

Everything here is gated on `user.is_admin`, which nothing in the product can
set — it is a column an operator changes directly in the database. There is no
"make me an admin" path on purpose: a privilege the app can grant is a
privilege an attacker can reach.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import notify, push
from ..auth import current_user
from ..db import get_session
from ..models import Announcement, NotificationTypeState, User, utcnow
from ..schemas import AnnouncementRequest, AnnouncementResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

#: An announcement reaches this many people at most in one call. Past it the
#: send is truncated rather than left to run for minutes inside a request —
#: the point at which that matters is the point to move it to a worker.
MAX_ANNOUNCEMENT_RECIPIENTS = 2000


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        # 404, not 403: the admin surface does not announce its own existence.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="not found")
    return user


@router.get("/overview")
def overview(session: Session = Depends(get_session),
             admin: User = Depends(require_admin)) -> dict:
    """What the operator needs to see before sending anything."""
    from sqlalchemy import func

    from ..models import PushSubscription

    users = session.scalar(select(func.count()).select_from(User)) or 0
    devices = session.scalar(
        select(func.count()).select_from(PushSubscription)) or 0
    return {
        "push_configured": push.is_configured(),
        "users": users,
        "registered_devices": devices,
        "daily_cap": notify.DAILY_CAP,
    }


# --- the master switches ----------------------------------------------
@router.get("/notification-types")
def list_types(session: Session = Depends(get_session),
               admin: User = Depends(require_admin)) -> list[dict]:
    """Every category, and whether it is switched on for everyone.

    This is the control that makes a noisy rule recoverable: turning one off
    stops it product-wide without a deploy.
    """
    notify.sync_categories(session)
    states = {
        row.category: row.enabled
        for row in session.scalars(select(NotificationTypeState))
    }
    return [
        {
            "category": category.key,
            "label": category.label,
            "enabled": states.get(category.key, True),
            "default_enabled": category.default_enabled,
        }
        for category in notify.CATEGORIES.values()
    ]


@router.put("/notification-types/{category}")
def set_type_enabled(category: str, enabled: bool = Query(...),
                     session: Session = Depends(get_session),
                     admin: User = Depends(require_admin)) -> dict:
    if category not in notify.CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")

    row = session.get(NotificationTypeState, category)
    if row is None:
        row = NotificationTypeState(category=category)
    row.enabled = enabled
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    logger.info("admin %s set category %s to enabled=%s", admin.id, category,
                enabled)
    return {"category": category, "enabled": enabled}


# --- announcements -----------------------------------------------------
@router.post("/announcements", response_model=AnnouncementResponse,
             status_code=status.HTTP_201_CREATED)
def send_announcement(request: AnnouncementRequest,
                      session: Session = Depends(get_session),
                      admin: User = Depends(require_admin)) -> Announcement:
    """Write a message and deliver it.

    `audience: "self"` sends only to the author's own devices. That is the
    intended first step for every announcement: a message to everyone cannot
    be recalled, and reading it on a real phone is the only way to catch a
    line that is too long or a link that is wrong.
    """
    announcement = Announcement(
        title=request.title, body=request.body, url=request.url,
        audience=request.audience, created_by=admin.id,
    )
    session.add(announcement)
    session.commit()

    recipients: list[User]
    if request.audience == "self":
        recipients = [admin]
    else:
        recipients = list(session.scalars(
            select(User).limit(MAX_ANNOUNCEMENT_RECIPIENTS)))

    url = request.url or "/activity"
    sent = 0
    for recipient in recipients:
        # The in-app record goes to everyone the category allows, whether or
        # not their phone is reachable; push is the courtesy on top.
        if request.audience == "self":
            notify.record(session, recipient.id, notify.ANNOUNCEMENT)
            if notify.deliver(session, recipient, notify.ANNOUNCEMENT,
                              request.title, request.body, url, force=True):
                sent += 1
        else:
            if not notify.user_wants(session, recipient, notify.ANNOUNCEMENT):
                continue
            notify.record(session, recipient.id, notify.ANNOUNCEMENT)
            if notify.deliver(session, recipient, notify.ANNOUNCEMENT,
                              request.title, request.body, url):
                sent += 1

    announcement.sent_at = utcnow()
    announcement.recipient_count = sent
    session.add(announcement)
    session.commit()
    logger.info("admin %s sent announcement %s to %s device owners",
                admin.id, announcement.id, sent)
    return announcement


@router.get("/announcements", response_model=list[AnnouncementResponse])
def list_announcements(limit: int = Query(20, ge=1, le=100),
                       session: Session = Depends(get_session),
                       admin: User = Depends(require_admin)) -> list[Announcement]:
    return list(session.scalars(
        select(Announcement).order_by(Announcement.created_at.desc())
        .limit(limit)))
