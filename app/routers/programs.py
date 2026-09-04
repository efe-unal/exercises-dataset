"""Saved programs: generate, store, list, read, activate and delete."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from engine.programs import Profile, generate

from ..auth import current_user
from ..db import get_session
from ..models import Program, User
from ..schemas import ProgramRequest, ProgramSummary, SaveProgramRequest

router = APIRouter(prefix="/v1/programs", tags=["programs"])

# Free accounts may keep one block at a time; generating is unlimited, only
# storage is capped. That keeps the free tier genuinely usable while giving
# the paid tier something concrete.
FREE_PROGRAM_LIMIT = 1


def _profile_from(request: ProgramRequest) -> Profile:
    return Profile(
        goal=request.goal, level=request.level,
        days_per_week=request.days_per_week, equipment=request.equipment,
        session_minutes=request.session_minutes, weeks=request.weeks,
        language=request.language, seed=request.seed,
        exclude_patterns=tuple(request.exclude_patterns),
    )


def _generate(request: ProgramRequest) -> dict:
    try:
        return generate(_profile_from(request))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(exc)) from exc


def _default_name(plan: dict) -> str:
    profile = plan["profile"]
    return f"{plan['split']} — {profile['goal'].replace('_', ' ')}"


def _summary(program: Program) -> ProgramSummary:
    profile = json.loads(program.profile_json)
    return ProgramSummary(
        id=program.id, name=program.name, is_active=program.is_active,
        created_at=program.created_at, goal=profile["goal"],
        level=profile["level"], days_per_week=profile["days_per_week"],
        weeks=profile["weeks"],
    )


def _owned(session: Session, user: User, program_id: str) -> Program:
    program = session.get(Program, program_id)
    if program is None or program.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="program not found")
    return program


@router.post("/preview")
def preview(request: ProgramRequest) -> dict:
    """Generate a block without saving it — no account required.

    This is what makes the product demonstrable: a visitor can see a real
    program before deciding whether to sign up.
    """
    return _generate(request)


@router.post("", response_model=ProgramSummary,
             status_code=status.HTTP_201_CREATED)
def save(request: SaveProgramRequest,
         session: Session = Depends(get_session),
         user: User = Depends(current_user)) -> ProgramSummary:
    stored = session.scalars(
        select(Program).where(Program.user_id == user.id)).all()
    if user.tier == "free" and len(stored) >= FREE_PROGRAM_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(f"free accounts can keep {FREE_PROGRAM_LIMIT} program; "
                    "delete it or upgrade to keep more"),
        )

    plan = _generate(request)
    if request.make_active:
        session.execute(update(Program).where(Program.user_id == user.id)
                        .values(is_active=False))

    program = Program(
        user_id=user.id,
        name=request.name or _default_name(plan),
        profile_json=json.dumps(plan["profile"], ensure_ascii=False),
        plan_json=json.dumps(plan, ensure_ascii=False),
        is_active=request.make_active,
    )
    session.add(program)
    session.commit()
    return _summary(program)


@router.get("", response_model=list[ProgramSummary])
def list_programs(session: Session = Depends(get_session),
                  user: User = Depends(current_user)) -> list[ProgramSummary]:
    programs = session.scalars(
        select(Program).where(Program.user_id == user.id)
        .order_by(Program.created_at.desc())).all()
    return [_summary(program) for program in programs]


@router.get("/active")
def active_program(session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> dict:
    """The block the athlete is currently training — what a client opens on."""
    program = session.scalar(
        select(Program).where(Program.user_id == user.id,
                              Program.is_active.is_(True))
        .order_by(Program.created_at.desc()))
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="no active program")
    return {"id": program.id, "name": program.name,
            "created_at": program.created_at.isoformat(),
            **json.loads(program.plan_json)}


@router.get("/{program_id}")
def get_program(program_id: str, session: Session = Depends(get_session),
                user: User = Depends(current_user)) -> dict:
    program = _owned(session, user, program_id)
    return {"id": program.id, "name": program.name,
            "is_active": program.is_active,
            "created_at": program.created_at.isoformat(),
            **json.loads(program.plan_json)}


@router.post("/{program_id}/activate", response_model=ProgramSummary)
def activate(program_id: str, session: Session = Depends(get_session),
             user: User = Depends(current_user)) -> ProgramSummary:
    program = _owned(session, user, program_id)
    session.execute(update(Program).where(Program.user_id == user.id)
                    .values(is_active=False))
    program.is_active = True
    session.add(program)
    session.commit()
    return _summary(program)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: str, session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> None:
    program = _owned(session, user, program_id)
    session.delete(program)
    session.commit()
