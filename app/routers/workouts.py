"""Workout logging, history and the load suggestions derived from it."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from engine.catalog import get_catalog

from ..auth import current_user
from ..db import get_session
from ..models import BodyMetric, Program, SetLog, User, WorkoutSession, utcnow
from ..progression import estimated_1rm, suggest_next
from ..schemas import BodyMetricRequest, LogSessionRequest, SessionResponse

router = APIRouter(prefix="/v1/workouts", tags=["workouts"])


def _owned_program(session: Session, user: User, program_id: str) -> Program:
    program = session.get(Program, program_id)
    if program is None or program.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="program not found")
    return program


@router.post("/sessions", response_model=SessionResponse,
             status_code=status.HTTP_201_CREATED)
def log_session(request: LogSessionRequest,
                session: Session = Depends(get_session),
                user: User = Depends(current_user)) -> WorkoutSession:
    """Record one training day.

    Logging the same slot twice replaces the earlier record rather than
    duplicating it — an athlete correcting a mistyped weight expects a fix,
    not a second workout in their history.
    """
    _owned_program(session, user, request.program_id)

    existing = session.scalar(
        select(WorkoutSession).where(
            WorkoutSession.program_id == request.program_id,
            WorkoutSession.week == request.week,
            WorkoutSession.day_index == request.day_index,
        ))
    if existing is not None:
        session.delete(existing)
        session.flush()

    workout = WorkoutSession(
        user_id=user.id, program_id=request.program_id, week=request.week,
        day_index=request.day_index, day_name=request.day_name,
        notes=request.notes,
        completed_at=utcnow() if request.completed else None,
    )
    session.add(workout)
    session.flush()

    for entry in request.sets:
        session.add(SetLog(
            user_id=user.id, session_id=workout.id,
            exercise_id=entry.exercise_id, exercise_name=entry.exercise_name,
            set_index=entry.set_index, reps=entry.reps,
            weight_kg=entry.weight_kg, rir=entry.rir,
            is_warmup=entry.is_warmup,
        ))
    session.commit()
    session.refresh(workout)
    return workout


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(program_id: str | None = None,
                  limit: int = Query(30, ge=1, le=200),
                  offset: int = Query(0, ge=0),
                  session: Session = Depends(get_session),
                  user: User = Depends(current_user)) -> list[WorkoutSession]:
    query = (select(WorkoutSession)
             .where(WorkoutSession.user_id == user.id)
             .options(selectinload(WorkoutSession.sets))
             .order_by(WorkoutSession.started_at.desc())
             .limit(limit).offset(offset))
    if program_id:
        query = query.where(WorkoutSession.program_id == program_id)
    return list(session.scalars(query))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, session: Session = Depends(get_session),
                   user: User = Depends(current_user)) -> None:
    workout = session.get(WorkoutSession, session_id)
    if workout is None or workout.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="session not found")
    session.delete(workout)
    session.commit()


@router.get("/next/{program_id}")
def next_session(program_id: str, session: Session = Depends(get_session),
                 user: User = Depends(current_user)) -> dict:
    """The next training day, with a load suggestion per exercise.

    This is the endpoint a client opens when the athlete walks into the gym:
    it works out where they are in the block and what to lift, using their own
    logged history rather than the static plan alone.
    """
    program = _owned_program(session, user, program_id)
    plan = json.loads(program.plan_json)
    weeks = plan["weeks"]

    logged = {(row.week, row.day_index) for row in session.scalars(
        select(WorkoutSession).where(WorkoutSession.program_id == program_id))}

    target = None
    for week in weeks:
        for day_index, day in enumerate(week["days"]):
            if (week["week"], day_index) not in logged:
                target = (week, day_index, day)
                break
        if target:
            break

    if target is None:
        return {"program_id": program_id, "complete": True,
                "message": "Every session in this block is logged. "
                           "Time to generate the next one."}

    week, day_index, day = target
    catalog = get_catalog()
    exercises = []
    for entry in day["exercises"]:
        exercise_id = entry["exercise"]["id"]
        rx = entry["prescription"]
        record = catalog.by_id.get(exercise_id, {})
        suggestion = suggest_next(
            session, user.id, exercise_id, rx["rep_min"], rx["rep_max"],
            pattern=record.get("pattern", "core"),
            mechanic=record.get("mechanic", "isolation"),
        )
        exercises.append({**entry, "suggestion": suggestion.as_dict()})

    return {
        "program_id": program_id,
        "complete": False,
        "week": week["week"],
        "day_index": day_index,
        "is_deload": week["is_deload"],
        "guidance": week["guidance"],
        # Plans saved before the keys existed have none; the English label
        # still ships, so a client falls back to it rather than breaking.
        "guidance_key": week.get("guidance_key", ""),
        "day": {"name": day["name"],
                "key": day.get("key", ""),
                "estimated_minutes": day["estimated_minutes"],
                "exercises": exercises},
        "attribution": plan["attribution"],
    }


@router.get("/suggestion/{exercise_id}")
def exercise_suggestion(exercise_id: str,
                        rep_min: int = Query(8, ge=1, le=100),
                        rep_max: int = Query(12, ge=1, le=100),
                        session: Session = Depends(get_session),
                        user: User = Depends(current_user)) -> dict:
    """The next load for one exercise, independent of any program day.

    An exercise detail screen needs this: the athlete is looking at one
    movement and wants to know what to put on the bar, whether or not it
    appears in today's session.
    """
    if rep_min > rep_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="rep_min cannot exceed rep_max")
    record = get_catalog().by_id.get(exercise_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="exercise not found")
    suggestion = suggest_next(
        session, user.id, exercise_id, rep_min, rep_max,
        pattern=record["pattern"], mechanic=record["mechanic"],
    )
    return {"exercise_name": record["name"], **suggestion.as_dict()}


@router.get("/history/{exercise_id}")
def exercise_history(exercise_id: str,
                     limit: int = Query(50, ge=1, le=200),
                     session: Session = Depends(get_session),
                     user: User = Depends(current_user)) -> dict:
    """Every logged set for one exercise, with its estimated one-rep max.

    The estimate is what a progress chart plots: it folds load and reps into
    one number, so a set of 8 at 80 kg is comparable with a set of 5 at 90.
    """
    logs = list(session.scalars(
        select(SetLog)
        .where(SetLog.user_id == user.id, SetLog.exercise_id == exercise_id)
        .order_by(SetLog.performed_at.desc()).limit(limit)))
    return {
        "exercise_id": exercise_id,
        "sets": [{
            "performed_at": log.performed_at.isoformat(),
            "set_index": log.set_index,
            "reps": log.reps,
            "weight_kg": log.weight_kg,
            "rir": log.rir,
            "is_warmup": log.is_warmup,
            "estimated_1rm": (round(estimated_1rm(log.weight_kg, log.reps), 1)
                              if log.weight_kg else None),
        } for log in logs],
    }


@router.get("/stats")
def stats(session: Session = Depends(get_session),
          user: User = Depends(current_user)) -> dict:
    """Headline numbers for a home screen."""
    total_sessions = session.scalar(
        select(func.count()).select_from(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)) or 0
    total_sets = session.scalar(
        select(func.count()).select_from(SetLog)
        .where(SetLog.user_id == user.id, SetLog.is_warmup.is_(False))) or 0
    volume = session.scalar(
        select(func.sum(SetLog.weight_kg * SetLog.reps))
        .where(SetLog.user_id == user.id, SetLog.is_warmup.is_(False))) or 0.0
    last = session.scalar(
        select(func.max(WorkoutSession.started_at))
        .where(WorkoutSession.user_id == user.id))
    return {
        "total_sessions": total_sessions,
        "total_working_sets": total_sets,
        "total_volume_kg": round(float(volume), 1),
        "last_session_at": last.isoformat() if last else None,
    }


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
def record_metric(request: BodyMetricRequest,
                  session: Session = Depends(get_session),
                  user: User = Depends(current_user)) -> dict:
    metric = BodyMetric(user_id=user.id, metric=request.metric,
                        value=request.value, unit=request.unit)
    if request.recorded_at is not None:
        metric.recorded_at = request.recorded_at
    session.add(metric)
    session.commit()
    return {"id": metric.id, "recorded_at": metric.recorded_at.isoformat()}


@router.get("/metrics")
def list_metrics(metric: str | None = None,
                 limit: int = Query(100, ge=1, le=500),
                 session: Session = Depends(get_session),
                 user: User = Depends(current_user)) -> list[dict]:
    query = (select(BodyMetric).where(BodyMetric.user_id == user.id)
             .order_by(BodyMetric.recorded_at.desc()).limit(limit))
    if metric:
        query = query.where(BodyMetric.metric == metric)
    return [{"metric": row.metric, "value": row.value, "unit": row.unit,
             "recorded_at": row.recorded_at.isoformat()}
            for row in session.scalars(query)]
