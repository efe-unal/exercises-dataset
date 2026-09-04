"""Set/rep/rest/effort prescription and week-to-week progression.

This is the part the raw dataset has nothing to say about: given a goal, a
training age and a slot in a session, how much work to prescribe and how to
advance it across a mesocycle.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

GOALS = ("strength", "hypertrophy", "endurance", "fat_loss", "general_fitness")
LEVELS = ("beginner", "intermediate", "advanced")


@dataclass(frozen=True)
class Prescription:
    sets: int
    rep_min: int
    rep_max: int
    rest_seconds: int
    rir: int          # reps in reserve — how far from failure to stop
    tempo: str        # eccentric-pause-concentric-pause, in seconds

    def as_dict(self) -> dict:
        return asdict(self)


# Base prescription per goal, for a *primary* compound lift.
_GOAL_BASE: dict[str, Prescription] = {
    "strength": Prescription(5, 3, 5, 180, 2, "3-1-1-0"),
    "hypertrophy": Prescription(4, 8, 12, 90, 1, "3-0-1-0"),
    "endurance": Prescription(3, 15, 20, 45, 2, "2-0-1-0"),
    "fat_loss": Prescription(3, 12, 15, 45, 2, "2-0-1-0"),
    "general_fitness": Prescription(3, 8, 12, 75, 2, "2-0-1-0"),
}

# Accessory and isolation work is never prescribed like the main lift: lighter,
# higher reps, shorter rest, further from failure early in a block.
_ROLE_ADJUST = {
    "primary": {"sets": 0, "reps": 0, "rest": 1.0},
    "accessory": {"sets": -1, "reps": 3, "rest": 0.7},
    "mobility": {"sets": -1, "reps": 0, "rest": 0.5},
}

# Beginners need less volume and more margin from failure; advanced lifters
# tolerate (and need) more.
_LEVEL_ADJUST = {
    "beginner": {"sets": -1, "rir": 1},
    "intermediate": {"sets": 0, "rir": 0},
    "advanced": {"sets": 1, "rir": -1},
}


def prescribe(goal: str, level: str, role: str, mechanic: str) -> Prescription:
    """Return the prescription for one exercise slot."""
    if goal not in GOALS:
        raise ValueError(f"unknown goal: {goal}")
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")

    base = _GOAL_BASE[goal]
    role_adj = _ROLE_ADJUST.get(role, _ROLE_ADJUST["accessory"])
    level_adj = _LEVEL_ADJUST[level]

    sets = max(2, base.sets + role_adj["sets"] + level_adj["sets"])
    rep_min = base.rep_min + role_adj["reps"]
    rep_max = base.rep_max + role_adj["reps"]

    # Isolation work is never worth heavy low-rep sets, whatever the goal.
    if mechanic == "isolation" and rep_min < 8:
        rep_min, rep_max = 8, max(12, rep_max)

    rest = int(base.rest_seconds * role_adj["rest"] / 5) * 5
    rir = max(0, base.rir + level_adj["rir"])

    return Prescription(sets, rep_min, rep_max, max(30, rest), rir, base.tempo)


# --- progression -------------------------------------------------------

# Load increments in kg for the next session, once the top of the rep range is
# hit for every set. Upper-body and isolation work advances in smaller jumps.
LOAD_STEP_KG = {
    ("compound", "lower"): 5.0,
    ("compound", "upper"): 2.5,
    ("isolation", "lower"): 2.5,
    ("isolation", "upper"): 1.25,
}

_LOWER_PATTERNS = {"squat", "hinge", "lunge", "calf"}


def load_step_kg(pattern: str, mechanic: str) -> float:
    half = "lower" if pattern in _LOWER_PATTERNS else "upper"
    return LOAD_STEP_KG[(mechanic, half)]


def progression_model(level: str) -> str:
    """Which progression scheme suits this training age."""
    return {
        "beginner": "linear_load",      # add load every session while it works
        "intermediate": "double",       # reps to the top of range, then load
        "advanced": "volume_wave",      # ramp volume across the block, deload
    }[level]


def week_modifier(model: str, week: int, weeks: int) -> dict:
    """How week ``week`` (1-based) differs from the block's baseline.

    Returns multipliers/deltas the caller applies to a base prescription.
    """
    is_deload = weeks >= 4 and week == weeks
    if is_deload:
        return {"set_delta": -1, "load_pct": 0.85, "rir_delta": 2,
                "key": "deload",
                "note": "Deload — cut volume, keep the movement pattern."}

    if model == "linear_load":
        return {"set_delta": 0, "load_pct": 1.0, "rir_delta": 0,
                "key": "linear_load",
                "note": "Add the smallest load step whenever every set hits "
                        "the top of the rep range."}
    if model == "double":
        return {"set_delta": 0, "load_pct": 1.0, "rir_delta": 0,
                "key": "double",
                "note": "Work reps up to the top of the range at the same "
                        "load, then add one load step and drop back to the "
                        "bottom of the range."}
    # volume_wave: add a set every week until the deload.
    return {"set_delta": week - 1, "load_pct": 1.0, "rir_delta": -min(week - 1, 2),
            "key": "volume_wave",
            "note": "Volume ramps each week; effort rises as reps in reserve "
                    "fall toward the deload."}
