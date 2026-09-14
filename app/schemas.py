"""Request and response shapes for the stateful endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from engine.prescription import GOALS, LEVELS


# --- accounts ---------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", max_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    username: str | None = None
    bio: str | None = None
    timezone: str = "UTC"
    is_admin: bool = False
    language: str
    unit_system: str
    tier: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=8)
    unit_system: Literal["metric", "imperial"] | None = None
    # Claiming a handle is what creates a public profile; until then the
    # account has none. Validated in app/social.py, not here, because the
    # rules include a reserved list and a uniqueness check.
    username: str | None = Field(default=None, min_length=3, max_length=30)
    bio: str | None = Field(default=None, max_length=300)


# --- social -----------------------------------------------------------
class ProfileSummary(BaseModel):
    username: str
    display_name: str
    bio: str | None = None
    followers: int
    following: int


class PublishedExercise(BaseModel):
    exercise_id: str
    name: str
    sets: int
    best_weight_kg: float | None
    total_reps: int


class PublishedSession(BaseModel):
    id: str
    day_name: str
    caption: str | None
    published_at: datetime | None
    performed_at: datetime
    total_sets: int
    total_volume_kg: float
    exercises: list[PublishedExercise]


class ProfileResponse(BaseModel):
    profile: ProfileSummary
    is_self: bool
    is_following: bool
    sessions: list[PublishedSession]


class PublishRequest(BaseModel):
    caption: str | None = Field(default=None, max_length=280)


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(max_length=700)
    keys: PushKeys


class NotificationPreference(BaseModel):
    category: str
    label: str
    enabled: bool
    available: bool


class PreferenceUpdate(BaseModel):
    category: str = Field(max_length=60)
    enabled: bool


class QuietHoursUpdate(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    quiet_from_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_to_hour: int | None = Field(default=None, ge=0, le=23)


class AnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=300)
    # "self" is the test send; it is the default so a mistyped request
    # cannot reach everyone.
    audience: Literal["self", "all"] = "self"


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    body: str
    url: str | None
    audience: str
    created_at: datetime
    sent_at: datetime | None
    recipient_count: int

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: str
    kind: str
    created_at: datetime
    read_at: datetime | None
    actor_username: str | None
    actor_display_name: str | None
    session_id: str | None


# --- programs ---------------------------------------------------------
class ProgramRequest(BaseModel):
    """The athlete profile a block is generated from."""

    goal: Literal[GOALS] = "hypertrophy"  # type: ignore[valid-type]
    level: Literal[LEVELS] = "beginner"  # type: ignore[valid-type]
    days_per_week: int = Field(3, ge=2, le=6)
    equipment: str | list[str] = "full_gym"
    session_minutes: int = Field(60, ge=20, le=180)
    weeks: int = Field(4, ge=1, le=12)
    language: str = "en"
    seed: int | None = None
    exclude_patterns: list[str] = Field(default_factory=list)


class SaveProgramRequest(ProgramRequest):
    name: str | None = Field(default=None, max_length=200)
    make_active: bool = True


class ProgramSummary(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: datetime
    goal: str
    level: str
    days_per_week: int
    weeks: int


# --- workout logging --------------------------------------------------
class SetEntry(BaseModel):
    exercise_id: str = Field(max_length=16)
    exercise_name: str = Field(max_length=200)
    set_index: int = Field(ge=1, le=50)
    reps: int = Field(ge=0, le=500)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    rir: int | None = Field(default=None, ge=0, le=10)
    is_warmup: bool = False


class LogSessionRequest(BaseModel):
    program_id: str
    week: int = Field(ge=1, le=12)
    day_index: int = Field(ge=0, le=6)
    day_name: str = Field(max_length=120)
    sets: list[SetEntry] = Field(min_length=1)
    notes: str | None = None
    completed: bool = True


class SetResponse(BaseModel):
    exercise_id: str
    exercise_name: str
    set_index: int
    reps: int
    weight_kg: float | None
    rir: int | None
    is_warmup: bool

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    program_id: str
    week: int
    day_index: int
    day_name: str
    started_at: datetime
    completed_at: datetime | None
    notes: str | None
    sets: list[SetResponse]

    model_config = {"from_attributes": True}


class BodyMetricRequest(BaseModel):
    metric: str = Field(max_length=40)
    value: float
    unit: str = Field(max_length=16)
    recorded_at: datetime | None = None
