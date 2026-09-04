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
