"""Log-aware progression: what to lift next, based on what was lifted before.

The engine's static plan says "4 sets of 8-12". This module answers the
question that actually matters in the gym — *at what weight* — by reading the
athlete's own history for that exercise.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.prescription import load_step_kg

from .models import SetLog

# How far a load is cut when the athlete misses the bottom of the rep range.
# A tenth is the smallest cut that reliably restores the target reps without
# throwing away a week of progress.
_MISS_DEDUCTION = 0.10

# Two failed sessions at one load is a stall; a third attempt rarely succeeds.
_STALL_SESSIONS = 2


@dataclass(frozen=True)
class Suggestion:
    """What to do next for one exercise."""

    exercise_id: str
    action: str            # establish | add_load | repeat | deload
    weight_kg: float | None
    rep_min: int
    rep_max: int
    reason: str
    last_performed_at: datetime | None = None
    best_estimated_1rm: float | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        if self.last_performed_at is not None:
            data["last_performed_at"] = self.last_performed_at.isoformat()
        return data


def estimated_1rm(weight_kg: float, reps: int) -> float:
    """Epley's formula.

    Reasonable up to about ten reps and useless beyond that, so callers should
    treat a high-rep estimate as a trend line rather than a real maximum.
    """
    return weight_kg * (1 + reps / 30)


def _working_sets(logs: list[SetLog]) -> list[SetLog]:
    return [log for log in logs if not log.is_warmup]


def _group_by_session(logs: list[SetLog]) -> list[list[SetLog]]:
    """Split a history into sessions, newest first, preserving set order."""
    sessions: dict[str, list[SetLog]] = {}
    for log in logs:
        sessions.setdefault(log.session_id, []).append(log)
    ordered = sorted(sessions.values(),
                     key=lambda group: max(log.performed_at for log in group),
                     reverse=True)
    return [sorted(group, key=lambda log: log.set_index) for group in ordered]


def history_for(session: Session, user_id: str, exercise_id: str,
                limit: int = 60) -> list[SetLog]:
    """Recent sets for one exercise, newest first."""
    return list(session.scalars(
        select(SetLog)
        .where(SetLog.user_id == user_id, SetLog.exercise_id == exercise_id)
        .order_by(SetLog.performed_at.desc())
        .limit(limit)
    ))


def suggest_next(session: Session, user_id: str, exercise_id: str,
                 rep_min: int, rep_max: int,
                 pattern: str = "core", mechanic: str = "isolation",
                 ) -> Suggestion:
    """Decide the next load for one exercise from the athlete's own history.

    The scheme is double progression: work the reps up to the top of the range
    at a fixed load, then add one load step and start again at the bottom.
    """
    logs = _working_sets(history_for(session, user_id, exercise_id))
    if not logs:
        return Suggestion(
            exercise_id=exercise_id, action="establish", weight_kg=None,
            rep_min=rep_min, rep_max=rep_max,
            reason=("No history yet. Work up to a weight you could stop "
                    f"{rep_max - rep_min + 1} reps short of failure, and treat "
                    "that as the starting load."),
        )

    sessions = _group_by_session(logs)
    latest = sessions[0]
    step = load_step_kg(pattern, mechanic)
    best = max((estimated_1rm(log.weight_kg, log.reps)
                for log in logs if log.weight_kg), default=None)
    last_at = max(log.performed_at for log in latest)

    loads = [log.weight_kg for log in latest if log.weight_kg is not None]
    if not loads:
        # Bodyweight work: reps are the only lever, so progress them directly.
        top_reps = max(log.reps for log in latest)
        action = "add_load" if top_reps >= rep_max else "repeat"
        return Suggestion(
            exercise_id=exercise_id, action=action, weight_kg=None,
            rep_min=rep_min, rep_max=rep_max, last_performed_at=last_at,
            reason=("Bodyweight movement — progress by adding reps, then by "
                    "moving to a harder variation once the top of the range "
                    "is comfortable."),
        )

    working_load = max(loads)
    at_load = [log for log in latest if log.weight_kg == working_load]
    hit_top = all(log.reps >= rep_max for log in at_load)
    missed_bottom = sum(1 for log in at_load if log.reps < rep_min) >= 2

    if hit_top:
        return Suggestion(
            exercise_id=exercise_id, action="add_load",
            weight_kg=round(working_load + step, 2),
            rep_min=rep_min, rep_max=rep_max, last_performed_at=last_at,
            best_estimated_1rm=best,
            reason=(f"Every set reached {rep_max} reps at {working_load} kg. "
                    f"Add {step} kg and start again at {rep_min} reps."),
        )

    if missed_bottom:
        if _stalled(sessions, working_load, rep_min):
            reduced = round(working_load * (1 - _MISS_DEDUCTION), 1)
            return Suggestion(
                exercise_id=exercise_id, action="deload", weight_kg=reduced,
                rep_min=rep_min, rep_max=rep_max, last_performed_at=last_at,
                best_estimated_1rm=best,
                reason=(f"{working_load} kg has stalled below {rep_min} reps "
                        f"for {_STALL_SESSIONS} sessions. Drop to {reduced} kg "
                        "and build back up."),
            )
        return Suggestion(
            exercise_id=exercise_id, action="repeat", weight_kg=working_load,
            rep_min=rep_min, rep_max=rep_max, last_performed_at=last_at,
            best_estimated_1rm=best,
            reason=(f"Short of {rep_min} reps at {working_load} kg. Repeat the "
                    "same load before deciding anything."),
        )

    top_reps = max(log.reps for log in at_load)
    return Suggestion(
        exercise_id=exercise_id, action="repeat", weight_kg=working_load,
        rep_min=rep_min, rep_max=rep_max, last_performed_at=last_at,
        best_estimated_1rm=best,
        reason=(f"Inside the rep range at {working_load} kg — currently "
                f"{top_reps}. Keep the load and add reps until every set "
                f"reaches {rep_max}."),
    )


def _stalled(sessions: list[list[SetLog]], load: float, rep_min: int) -> bool:
    """True when the recent sessions all fell short at this same load."""
    checked = 0
    for group in sessions[:_STALL_SESSIONS]:
        at_load = [log for log in group if log.weight_kg == load]
        if not at_load or max(log.reps for log in at_load) >= rep_min:
            return False
        checked += 1
    return checked >= _STALL_SESSIONS
