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
    language: str
    unit_system: str
    tier: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=8)
    unit_system: Literal["metric", "imperial"] | None = None


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
