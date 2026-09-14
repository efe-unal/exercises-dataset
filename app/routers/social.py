"""Public profiles, publishing, following and notifications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from ..auth import current_user, optional_user
from ..db import get_session
from ..models import Notification, User, WorkoutSession, utcnow
from ..schemas import (
    NotificationResponse,
    ProfileResponse,
    ProfileSummary,
    PublishRequest,
    PublishedSession,
)
from ..social import (
    find_by_username,
    follow,
    follow_counts,
    followers_of,
    following_users,
    is_following,
    publish_session,
    published_sessions,
    unfollow,
    unpublish_session,
)

router = APIRouter(tags=["social"])

PROFILE_PAGE_SIZE = 20


def _summary(session: Session, user: User) -> ProfileSummary:
    followers, following = follow_counts(session, user.id)
    return ProfileSummary(
        username=user.username or "",
        display_name=user.display_name or user.username_display or "",
        bio=user.bio,
        followers=followers,
        following=following,
    )


def _public_session(workout: WorkoutSession) -> PublishedSession:
    """Trim a session to what a viewer may see.

    Built field by field rather than dumped from the model: the row carries
    the owner's user id and program id, and neither belongs in a public
    response.
    """
    working = [s for s in workout.sets if not s.is_warmup]
    volume = sum((s.weight_kg or 0) * s.reps for s in working)
    exercises: dict[str, dict] = {}
    for entry in working:
        row = exercises.setdefault(entry.exercise_id, {
            "exercise_id": entry.exercise_id,
            "name": entry.exercise_name,
            "sets": 0,
            "best_weight_kg": None,
            "total_reps": 0,
        })
        row["sets"] += 1
        row["total_reps"] += entry.reps
        if entry.weight_kg is not None:
            best = row["best_weight_kg"]
            row["best_weight_kg"] = (entry.weight_kg if best is None
                                     else max(best, entry.weight_kg))

    return PublishedSession(
        id=workout.id,
        day_name=workout.day_name,
        caption=workout.caption,
        published_at=workout.published_at,
        performed_at=workout.started_at,
        total_sets=len(working),
        total_volume_kg=round(float(volume), 1),
        exercises=list(exercises.values()),
    )


# --- profiles ----------------------------------------------------------
@router.get("/v1/profiles/{username}", response_model=ProfileResponse)
def read_profile(username: str,
                 limit: int = Query(PROFILE_PAGE_SIZE, ge=1, le=50),
                 offset: int = Query(0, ge=0),
                 session: Session = Depends(get_session),
                 viewer: User | None = Depends(optional_user)) -> ProfileResponse:
    """A public profile: who they are, and what they have published.

    Open to signed-out visitors, because a shared card has to lead somewhere
    for someone who does not have the app yet. Only published sessions ever
    appear, and the response carries no email and no private session.
    """
    user = find_by_username(session, username)
    sessions = published_sessions(session, user, limit, offset)
    # selectinload is not available through the helper, so the sets are
    # loaded lazily here; the page size is small and bounded.
    return ProfileResponse(
        profile=_summary(session, user),
        is_self=viewer is not None and viewer.id == user.id,
        is_following=(viewer is not None
                      and is_following(session, viewer.id, user.id)),
        sessions=[_public_session(workout) for workout in sessions],
    )


@router.get("/v1/profiles/{username}/sessions/{session_id}",
            response_model=PublishedSession)
def read_published_session(username: str, session_id: str,
                           session: Session = Depends(get_session)) -> PublishedSession:
    """One published session, by its own link — what a shared card points to."""
    user = find_by_username(session, username)
    workout = session.scalar(
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.sets))
        .where(WorkoutSession.id == session_id,
               WorkoutSession.user_id == user.id,
               WorkoutSession.published_at.is_not(None)))
    if workout is None:
        # Deliberately the same answer for "never existed", "not published"
        # and "unpublished since": a 403 would confirm the session exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no such published workout")
    return _public_session(workout)


# --- publishing --------------------------------------------------------
@router.post("/v1/workouts/sessions/{session_id}/publish",
             response_model=PublishedSession)
def publish(session_id: str, request: PublishRequest,
            session: Session = Depends(get_session),
            user: User = Depends(current_user)) -> PublishedSession:
    workout = session.get(WorkoutSession, session_id)
    if workout is None or workout.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="session not found")
    publish_session(session, user, workout, request.caption)
    session.refresh(workout)
    return _public_session(workout)


@router.delete("/v1/workouts/sessions/{session_id}/publish",
               status_code=status.HTTP_204_NO_CONTENT)
def unpublish(session_id: str, session: Session = Depends(get_session),
              user: User = Depends(current_user)) -> None:
    workout = session.get(WorkoutSession, session_id)
    if workout is None or workout.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="session not found")
    unpublish_session(session, workout)


# --- following ---------------------------------------------------------
@router.post("/v1/profiles/{username}/follow",
             status_code=status.HTTP_204_NO_CONTENT)
def follow_profile(username: str, session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> None:
    follow(session, user, find_by_username(session, username))


@router.delete("/v1/profiles/{username}/follow",
               status_code=status.HTTP_204_NO_CONTENT)
def unfollow_profile(username: str, session: Session = Depends(get_session),
                     user: User = Depends(current_user)) -> None:
    unfollow(session, user, find_by_username(session, username))


@router.get("/v1/me/following", response_model=list[ProfileSummary])
def list_following(limit: int = Query(50, ge=1, le=200),
                   offset: int = Query(0, ge=0),
                   session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> list[ProfileSummary]:
    return [_summary(session, other)
            for other in following_users(session, user.id, limit, offset)]


@router.get("/v1/me/followers", response_model=list[ProfileSummary])
def list_followers(limit: int = Query(50, ge=1, le=200),
                   offset: int = Query(0, ge=0),
                   session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> list[ProfileSummary]:
    return [_summary(session, other)
            for other in followers_of(session, user.id, limit, offset)]


# --- notifications -----------------------------------------------------
@router.get("/v1/notifications", response_model=list[NotificationResponse])
def list_notifications(unread_only: bool = False,
                       limit: int = Query(50, ge=1, le=200),
                       offset: int = Query(0, ge=0),
                       session: Session = Depends(get_session),
                       user: User = Depends(current_user)) -> list[NotificationResponse]:
    query = (select(Notification)
             .where(Notification.user_id == user.id)
             .order_by(Notification.created_at.desc())
             .limit(limit).offset(offset))
    if unread_only:
        query = query.where(Notification.read_at.is_(None))

    rows = list(session.scalars(query))
    actors = {
        actor.id: actor
        for actor in session.scalars(
            select(User).where(
                User.id.in_({row.actor_id for row in rows if row.actor_id})))
    } if rows else {}

    out = []
    for row in rows:
        actor = actors.get(row.actor_id) if row.actor_id else None
        out.append(NotificationResponse(
            id=row.id,
            kind=row.kind,
            created_at=row.created_at,
            read_at=row.read_at,
            actor_username=actor.username if actor else None,
            actor_display_name=(actor.display_name or actor.username_display
                                if actor else None),
            session_id=row.session_id,
        ))
    return out


@router.get("/v1/notifications/unread-count")
def unread_count(session: Session = Depends(get_session),
                 user: User = Depends(current_user)) -> dict:
    """What the badge on the tab bar reads."""
    from sqlalchemy import func

    count = session.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id,
               Notification.read_at.is_(None))) or 0
    return {"unread": count}


@router.post("/v1/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(session: Session = Depends(get_session),
              user: User = Depends(current_user)) -> None:
    """Mark everything read. Per-notification read state is not worth the
    round trips: opening the list is the act of reading them."""
    session.execute(
        update(Notification)
        .where(Notification.user_id == user.id,
               Notification.read_at.is_(None))
        .values(read_at=utcnow()))
    session.commit()
