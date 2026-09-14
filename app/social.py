"""The social layer: public handles, publishing, following and notifications.

The shape here is Spotify's, not Twitter's. There is no feed and no comment
thread. You publish a workout, someone opens your profile and sees it, and
following you means being told when you publish again — nothing more.

Two rules the rest of the module exists to enforce:

* **Nothing is public until it is published.** Not a session, not a profile.
  Following someone grants no access to anything they have not published.
* **A handle is the only public identifier.** Email never appears in a
  profile response, so sharing a link cannot leak an address.
"""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Follow, Notification, User, WorkoutSession, utcnow

# Letters, digits, underscore; must start with a letter or digit. Short enough
# to fit a share card, long enough to be findable.
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{2,29}$")

# Handles that would collide with a route or impersonate the product. Checked
# against the lowercased handle, so "Admin" is caught too.
RESERVED_USERNAMES = frozenset({
    "admin", "administrator", "api", "app", "auth", "root", "support",
    "help", "settings", "profile", "profiles", "me", "you", "user", "users",
    "login", "signin", "signup", "register", "logout", "password", "reset",
    "exercises", "programs", "workouts", "progress", "today", "notifications",
    "system", "official", "staff", "team", "null", "undefined", "about",
    "terms", "privacy", "security", "contact",
})

#: The category key, defined in app/notify.py so the preference switch, the
#: master switch and the stored notification all name the same thing. Two
#: spellings for one category meant the preference lookup silently failed.
NOTIFY_WORKOUT_PUBLISHED = "social.workout_published"

# One notification fan-out is bounded so a single publish cannot enqueue an
# unbounded number of rows. Beyond this the notification is skipped rather
# than the publish failing — the workout still goes public.
MAX_NOTIFICATION_FANOUT = 5000


class UsernameError(ValueError):
    """The requested handle cannot be used."""


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    """Return the normalized handle, or raise ``UsernameError``."""
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.match(normalized):
        raise UsernameError(
            "a username must be 3-30 characters, start with a letter or "
            "digit, and use only letters, digits and underscores"
        )
    if normalized in RESERVED_USERNAMES:
        raise UsernameError("that username is reserved")
    return normalized


def set_username(session: Session, user: User, username: str) -> User:
    """Claim a public handle for this account."""
    try:
        normalized = validate_username(username)
    except UsernameError as exc:
        # 422 as an integer: Starlette renamed its constant for this
        # code, and the number is stable across both versions.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    taken = session.scalar(
        select(User).where(User.username == normalized, User.id != user.id))
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="that username is already taken")

    user.username = normalized
    user.username_display = username.strip()
    session.add(user)
    session.commit()
    return user


def find_by_username(session: Session, username: str) -> User:
    user = session.scalar(
        select(User).where(User.username == normalize_username(username)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no such profile")
    return user


# --- publishing --------------------------------------------------------
def publish_session(session: Session, user: User,
                    workout: WorkoutSession,
                    caption: str | None) -> WorkoutSession:
    """Make one logged session visible on the athlete's profile.

    Requires a handle first: without one there is no profile for the workout
    to appear on, and a published-but-unreachable session would be a
    confusing lie.
    """
    if user.username is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="choose a username before publishing a workout",
        )
    already_public = workout.published_at is not None
    workout.caption = caption
    if not already_public:
        workout.published_at = utcnow()
    session.add(workout)
    session.commit()

    # Editing a caption is not news. Only a first publish notifies.
    if not already_public:
        _notify_followers(session, user, workout)
    return workout


def unpublish_session(session: Session, workout: WorkoutSession) -> WorkoutSession:
    """Take a session back off the profile.

    Notifications already sent are left alone but stop resolving, which is
    why they hold no foreign key to the session.
    """
    workout.published_at = None
    session.add(workout)
    session.commit()
    return workout


def _notify_followers(session: Session, actor: User,
                      workout: WorkoutSession) -> None:
    follower_ids = list(session.scalars(
        select(Follow.follower_id)
        .where(Follow.followee_id == actor.id)
        .limit(MAX_NOTIFICATION_FANOUT)))
    if not follower_ids:
        return
    # Imported here rather than at module scope: notify imports the models
    # this module also uses, and a top-level import would be circular.
    from . import notify as notifications

    followers = session.scalars(
        select(User).where(User.id.in_(follower_ids)))
    who = actor.display_name or f"@{actor.username}"
    for follower in followers:
        notifications.notify(
            session, follower, NOTIFY_WORKOUT_PUBLISHED,
            title=who,
            body=f"published {workout.day_name}",
            url=f"/@{actor.username}",
            actor_id=actor.id,
            session_id=workout.id,
        )


def published_sessions(session: Session, user: User, limit: int,
                       offset: int) -> list[WorkoutSession]:
    return list(session.scalars(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id,
               WorkoutSession.published_at.is_not(None))
        .order_by(WorkoutSession.published_at.desc())
        .limit(limit).offset(offset)))


# --- following ---------------------------------------------------------
def follow(session: Session, follower: User, followee: User) -> None:
    if follower.id == followee.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="you cannot follow yourself")
    existing = session.scalar(
        select(Follow).where(Follow.follower_id == follower.id,
                             Follow.followee_id == followee.id))
    if existing is not None:
        return  # following twice is the same as following once
    session.add(Follow(follower_id=follower.id, followee_id=followee.id))
    session.commit()


def unfollow(session: Session, follower: User, followee: User) -> None:
    existing = session.scalar(
        select(Follow).where(Follow.follower_id == follower.id,
                             Follow.followee_id == followee.id))
    if existing is not None:
        session.delete(existing)
        session.commit()


def is_following(session: Session, follower_id: str, followee_id: str) -> bool:
    return session.scalar(
        select(func.count()).select_from(Follow)
        .where(Follow.follower_id == follower_id,
               Follow.followee_id == followee_id)) > 0


def follow_counts(session: Session, user_id: str) -> tuple[int, int]:
    """Return ``(followers, following)``."""
    followers = session.scalar(
        select(func.count()).select_from(Follow)
        .where(Follow.followee_id == user_id)) or 0
    following = session.scalar(
        select(func.count()).select_from(Follow)
        .where(Follow.follower_id == user_id)) or 0
    return followers, following


def following_users(session: Session, user_id: str, limit: int,
                    offset: int) -> list[User]:
    return list(session.scalars(
        select(User).join(Follow, Follow.followee_id == User.id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit).offset(offset)))


def followers_of(session: Session, user_id: str, limit: int,
                 offset: int) -> list[User]:
    return list(session.scalars(
        select(User).join(Follow, Follow.follower_id == User.id)
        .where(Follow.followee_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit).offset(offset)))
