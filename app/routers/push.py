"""Push subscriptions and notification preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import notify, push
from ..auth import current_user
from ..db import get_session
from ..models import PushSubscription, User, utcnow
from ..schemas import (
    NotificationPreference,
    PreferenceUpdate,
    PushSubscriptionRequest,
    QuietHoursUpdate,
)

router = APIRouter(prefix="/v1/push", tags=["notifications"])


@router.get("/config")
def config() -> dict:
    """What a client needs before it can ask for permission.

    Returns `enabled: false` when no VAPID keys are set, so the app hides the
    whole thing rather than offering a button that cannot work.
    """
    return {"enabled": push.is_configured(), "public_key": push.public_key()}


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(request: PushSubscriptionRequest,
              user_agent: str | None = Header(default=None),
              session: Session = Depends(get_session),
              user: User = Depends(current_user)) -> None:
    """Register this browser for notifications.

    Re-subscribing the same browser yields the same endpoint, so an existing
    row is updated rather than duplicated — otherwise a person who reinstalls
    gets every notification twice.
    """
    existing = session.scalar(
        select(PushSubscription)
        .where(PushSubscription.endpoint == request.endpoint))

    if existing is not None:
        # The endpoint is unique across users: a shared device that changed
        # hands must not keep delivering to the previous account.
        existing.user_id = user.id
        existing.p256dh = request.keys.p256dh
        existing.auth = request.keys.auth
        existing.user_agent = (user_agent or "")[:300] or None
        existing.consecutive_failures = 0
        session.add(existing)
    else:
        session.add(PushSubscription(
            user_id=user.id, endpoint=request.endpoint,
            p256dh=request.keys.p256dh, auth=request.keys.auth,
            user_agent=(user_agent or "")[:300] or None,
        ))
    session.commit()


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(request: PushSubscriptionRequest,
                session: Session = Depends(get_session),
                user: User = Depends(current_user)) -> None:
    row = session.scalar(
        select(PushSubscription)
        .where(PushSubscription.endpoint == request.endpoint,
               PushSubscription.user_id == user.id))
    if row is not None:
        session.delete(row)
        session.commit()


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
def send_test(session: Session = Depends(get_session),
              user: User = Depends(current_user)) -> None:
    """Send one notification to the caller's own devices.

    Exists so a person can confirm notifications actually arrive on their
    phone — the permission prompt says nothing about whether delivery works.
    Bypasses preferences and quiet hours because they asked for it just now.
    """
    if not push.is_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="push is not configured on this server")
    sent = notify.deliver(session, user, notify.ANNOUNCEMENT,
                          title="Notifications are working",
                          body="This is what one looks like.",
                          url="/activity", force=True)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="no device is registered for notifications on this account",
        )


# --- preferences -------------------------------------------------------
@router.get("/preferences")
def read_preferences(session: Session = Depends(get_session),
                     user: User = Depends(current_user)) -> dict:
    return {
        "categories": notify.preferences_for(session, user),
        "timezone": user.timezone,
        "quiet_from_hour": user.quiet_from_hour,
        "quiet_to_hour": user.quiet_to_hour,
        "daily_cap": notify.DAILY_CAP,
    }


@router.put("/preferences", response_model=list[NotificationPreference])
def update_preference(request: PreferenceUpdate,
                      session: Session = Depends(get_session),
                      user: User = Depends(current_user)) -> list[dict]:
    try:
        notify.set_preference(session, user, request.category, request.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return notify.preferences_for(session, user)


@router.put("/quiet-hours")
def update_quiet_hours(request: QuietHoursUpdate,
                       session: Session = Depends(get_session),
                       user: User = Depends(current_user)) -> dict:
    """Set the window during which nothing is delivered, and the zone it is in.

    The timezone is validated rather than trusted: a bad one would make every
    quiet-hour comparison meaningless, which is exactly the failure that
    wakes someone at 03:00.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if request.timezone is not None:
        try:
            ZoneInfo(request.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400,
                                detail="unknown timezone") from exc
        user.timezone = request.timezone

    if request.quiet_from_hour is not None:
        user.quiet_from_hour = request.quiet_from_hour
    if request.quiet_to_hour is not None:
        user.quiet_to_hour = request.quiet_to_hour

    session.add(user)
    session.commit()
    return {
        "timezone": user.timezone,
        "quiet_from_hour": user.quiet_from_hour,
        "quiet_to_hour": user.quiet_to_hour,
        "updated_at": utcnow().isoformat(),
    }
