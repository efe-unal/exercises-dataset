"""ORM models: accounts, saved programs and the workout log.

The workout log is the important one. A generated program is only a plan; what
the athlete actually lifted is what drives the next session's load, so
``SetLog`` is the record everything else is derived from.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120), default=None)
    # Preferences the clients read back so a returning athlete keeps their
    # settings across devices.
    language: Mapped[str] = mapped_column(String(8), default="en")
    unit_system: Mapped[str] = mapped_column(String(8), default="metric")
    tier: Mapped[str] = mapped_column(String(16), default="free")
    # The public handle. Null until the person picks one, and until then they
    # have no profile at all — an account is fully usable without going
    # public. Stored lowercase; `username_display` keeps their capitalisation.
    username: Mapped[str | None] = mapped_column(String(30), unique=True,
                                                 index=True, default=None)
    username_display: Mapped[str | None] = mapped_column(String(30),
                                                         default=None)
    bio: Mapped[str | None] = mapped_column(String(300), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)

    tokens: Mapped[list["AuthToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
    programs: Mapped[list["Program"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class AuthToken(Base):
    """An opaque session token.

    Only the hash is stored, so a leaked database cannot be used to
    impersonate anyone. Rows are deletable, which is what makes logout and
    revocation real rather than cosmetic.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None)

    user: Mapped[User] = relationship(back_populates="tokens")


class PasswordResetToken(Base):
    """A single-use, short-lived token for choosing a new password.

    Separate from ``AuthToken`` deliberately: a reset token is not a session,
    must not be usable as one, and is consumed rather than expired.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                     default=None)


class Program(Base):
    """A generated block, saved so it can be trained through and logged against."""

    __tablename__ = "programs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # The request that produced the block, and the block itself, both as JSON
    # text. The plan is a snapshot: regenerating could pick different
    # exercises, and an athlete mid-block must not have their program change
    # under them.
    profile_json: Mapped[str] = mapped_column(Text)
    plan_json: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)

    user: Mapped[User] = relationship(back_populates="programs")
    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="program", cascade="all, delete-orphan")


class WorkoutSession(Base):
    """One training day, performed on one date."""

    __tablename__ = "workout_sessions"
    __table_args__ = (
        UniqueConstraint("program_id", "week", "day_index",
                         name="uq_session_slot"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[str] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    week: Mapped[int] = mapped_column(Integer)
    day_index: Mapped[int] = mapped_column(Integer)
    day_name: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Private unless explicitly published. Nothing a person logs becomes
    # visible to anyone else by default, and publishing is per session rather
    # than an account-wide switch.
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True)
    # A short line the athlete writes when publishing. Their own words about
    # their own workout — not a comment thread.
    caption: Mapped[str | None] = mapped_column(String(280), default=None)

    program: Mapped[Program] = relationship(back_populates="sessions")
    sets: Mapped[list["SetLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="SetLog.set_index")


class SetLog(Base):
    """One set actually performed — the ground truth progression reads from."""

    __tablename__ = "set_logs"
    __table_args__ = (
        Index("ix_setlog_user_exercise", "user_id", "exercise_id",
              "performed_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[str] = mapped_column(String(16), index=True)
    exercise_name: Mapped[str] = mapped_column(String(200))
    set_index: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    # Bodyweight work carries no load, so this stays null rather than lying
    # with a zero.
    weight_kg: Mapped[float | None] = mapped_column(Float, default=None)
    rir: Mapped[int | None] = mapped_column(Integer, default=None)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=utcnow)

    session: Mapped[WorkoutSession] = relationship(back_populates="sets")


class BodyMetric(Base):
    """Bodyweight and similar tracked numbers, for progress over a block."""

    __tablename__ = "body_metrics"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=utcnow, index=True)


class Follow(Base):
    """One person following another.

    Following grants no access to anything: it only decides who gets told
    when a workout is published. Private sessions stay private to followers
    and strangers alike.
    """

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follow_pair"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    follower_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    followee_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow)


class Notification(Base):
    """Something that happened which a person should be told about.

    Stored rather than pushed so the app can show a list on open. Delivery to
    a locked phone is a separate concern — see docs/SOCIAL.md.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    # Who receives it.
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    # Who caused it. Nullable so a system notice needs no actor.
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None)
    # What it points at. Nullable for the same reason. No foreign key: the
    # session may be unpublished or deleted later, and the notification
    # should survive that as a dead link rather than vanish or fail.
    session_id: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                     default=None)
