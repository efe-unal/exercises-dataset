"""Program generator — turns a goal into a full mesocycle.

Given an athlete profile (goal, training age, days per week, available
equipment, session length) it selects a split, fills each slot from the
catalog, prescribes sets/reps/rest/effort, and lays the block out week by week
with a progression model.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .catalog import Catalog, get_catalog
from .prescription import (
    GOALS,
    LEVELS,
    load_step_kg,
    prescribe,
    progression_model,
    week_modifier,
)
from .splits import Day, Slot, select_split

# Rough per-set cost in seconds, work plus rest, used to fit a session into the
# time the athlete actually has.
_SECONDS_PER_SET_OVERHEAD = 45

# Time is not the only limit on a session. Low-volume prescriptions leave room
# for a dozen movements inside an hour, but nobody trains a dozen movements in
# a session: past roughly eight the athlete is spreading effort thin and
# spending the time setting equipment up rather than lifting. Beyond the cap
# the right answer is more sets of what is already there, not more exercises.
_MIN_EXERCISES_PER_SESSION = 3
_MAX_EXERCISES_PER_SESSION = 8
_MINUTES_PER_EXERCISE = 10


def _exercise_cap(session_minutes: int) -> int:
    """How many distinct movements belong in a session of this length."""
    return max(
        _MIN_EXERCISES_PER_SESSION,
        min(_MAX_EXERCISES_PER_SESSION, session_minutes // _MINUTES_PER_EXERCISE),
    )


@dataclass
class Profile:
    goal: str = "hypertrophy"
    level: str = "beginner"
    days_per_week: int = 3
    equipment: object = "full_gym"      # profile name or explicit list
    session_minutes: int = 60
    weeks: int = 4
    language: str = "en"
    seed: int | None = None
    exclude_patterns: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.goal not in GOALS:
            raise ValueError(f"goal must be one of {GOALS}")
        if self.level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        if not 2 <= self.days_per_week <= 6:
            raise ValueError("days_per_week must be between 2 and 6")
        if not 20 <= self.session_minutes <= 180:
            raise ValueError("session_minutes must be between 20 and 180")
        if not 1 <= self.weeks <= 12:
            raise ValueError("weeks must be between 1 and 12")


# Equipment ranked by how well it serves a main lift. Anything unlisted scores
# 0, so a barbell bench press outranks an obscure machine variation.
_EQUIPMENT_SCORE = {
    "barbell": 6, "olympic barbell": 6, "trap bar": 5, "dumbbell": 5,
    "body weight": 4, "kettlebell": 4, "ez barbell": 4, "cable": 3,
    "leverage machine": 3, "smith machine": 2, "weighted": 2, "band": 2,
    "resistance band": 1, "assisted": 1,
}

# The dataset carries many near-duplicate variations; these markers flag the
# ones that are variants of a canonical lift rather than the lift itself.
_VARIANT_MARKERS = ("v. 2", "v. 3", "v. 4", "(male)", "(female)", "version")


def _candidate_score(exercise: dict, slot: Slot) -> float:
    """Rank candidates so canonical lifts are picked ahead of obscure ones."""
    score = float(_EQUIPMENT_SCORE.get(exercise["equipment"], 0))
    if exercise["role"] == slot.role:
        score += 3
    name = exercise["name"].lower()
    if any(marker in name for marker in _VARIANT_MARKERS):
        score -= 3
    # Long names are almost always heavily-qualified variations.
    score -= len(name.split()) * 0.25
    return score


def _pick(catalog: Catalog, slot: Slot, equipment, used: set[str],
          rng: random.Random, exclude_patterns: set[str],
          level: str) -> dict | None:
    """Fill one slot, preferring an exercise not already used in the block.

    Candidates are scored, then chosen at random from the top band so repeated
    generations vary without ever reaching for the worst option in the pool.
    Anything above the athlete's training age is filtered out entirely rather
    than merely ranked down: a novice should never be handed a muscle-up, even
    when it is the only movement left for a pattern. A slot with no
    level-appropriate option is dropped instead.
    """
    for pattern in slot.patterns:
        if pattern in exclude_patterns:
            continue
        for role in (slot.role, "accessory", None):
            candidates = catalog.find(pattern=pattern, role=role,
                                      equipment=equipment, exclude_ids=used,
                                      max_difficulty=level)
            if candidates:
                return _choose(candidates, slot, rng)
        # Nothing unused left for this pattern — repeating a movement is better
        # than dropping the pattern out of the program entirely.
        repeat = catalog.find(pattern=pattern, equipment=equipment,
                              max_difficulty=level)
        if repeat:
            return _choose(repeat, slot, rng)
    return None


def _choose(candidates: list[dict], slot: Slot, rng: random.Random) -> dict:
    ranked = sorted(candidates, key=lambda e: -_candidate_score(e, slot))
    band = ranked[:max(1, min(8, len(ranked) // 4 or 1))]
    return rng.choice(band)


def _localized_instructions(exercise: dict, language: str) -> dict:
    steps = exercise.get("instruction_steps") or {}
    text = exercise.get("instructions") or {}
    return {
        "language": language if language in text else "en",
        "text": text.get(language) or text.get("en"),
        "steps": steps.get(language) or steps.get("en") or [],
    }


def _entry(slot: Slot, exercise: dict, rx, profile: Profile) -> dict:
    """One line of a session: what to do, how to do it, how much."""
    return {
        "slot": slot.label,
        "exercise": {
            "id": exercise["id"],
            "name": exercise["name"],
            "body_part": exercise["body_part"],
            "target": exercise["target"],
            "equipment": exercise["equipment"],
            "pattern": exercise["pattern"],
            "mechanic": exercise["mechanic"],
            "role": exercise["role"],
            "difficulty": exercise["difficulty"],
            "image": exercise["image"],
            "gif_url": exercise["gif_url"],
            "attribution": exercise.get("attribution"),
        },
        "instructions": _localized_instructions(exercise, profile.language),
        "prescription": rx.as_dict(),
        "load_step_kg": load_step_kg(exercise["pattern"], exercise["mechanic"]),
    }


def _build_day(catalog: Catalog, day: Day, profile: Profile, equipment,
               used: set[str], rng: random.Random) -> dict:
    exclude = set(profile.exclude_patterns)
    cap = _exercise_cap(profile.session_minutes)
    entries: list[dict] = []
    for slot in day.slots:
        if len(entries) >= cap:
            break
        exercise = _pick(catalog, slot, equipment, used, rng, exclude,
                         profile.level)
        if exercise is None:
            continue
        rx = prescribe(profile.goal, profile.level, exercise["role"],
                       exercise["mechanic"])
        # Slots are ordered most- to least-important, so once the session is
        # full the rest are dropped rather than squeezed in. The first few
        # always stay: a day with fewer movements than that is not a session.
        candidate = {"prescription": rx.as_dict()}
        if (len(entries) >= _MIN_EXERCISES_PER_SESSION
                and _estimate_minutes(entries + [candidate]) > profile.session_minutes):
            break
        used.add(exercise["id"])
        entries.append(_entry(slot, exercise, rx, profile))
    _top_up(catalog, day, profile, equipment, used, rng, entries)
    return {"name": day.name, "exercises": entries,
            "estimated_minutes": _estimate_minutes(entries)}


def _top_up(catalog: Catalog, day: Day, profile: Profile, equipment,
            used: set[str], rng: random.Random, entries: list[dict]) -> None:
    """Spend leftover session time on accessory work for the day's patterns.

    A template has a fixed number of slots, so a long session against a short
    template would otherwise finish well under the athlete's available time.
    """
    exclude = set(profile.exclude_patterns)
    cap = _exercise_cap(profile.session_minutes)
    if len(entries) >= cap:
        return
    day_patterns = [p for slot in day.slots for p in slot.patterns
                    if p not in exclude]
    if not day_patterns:
        return
    for pattern in day_patterns * 2:  # two passes before giving up
        if len(entries) >= cap:
            return
        filler = Slot(patterns=(pattern,), role="accessory",
                      label=f"Accessory — {pattern.replace('_', ' ')}")
        exercise = _pick(catalog, filler, equipment, used, rng, exclude,
                         profile.level)
        if exercise is None or exercise["id"] in used:
            continue
        rx = prescribe(profile.goal, profile.level, "accessory",
                       exercise["mechanic"])
        if _estimate_minutes(entries + [{"prescription": rx.as_dict()}]) > profile.session_minutes:
            return
        used.add(exercise["id"])
        entries.append(_entry(filler, exercise, rx, profile))


def _estimate_minutes(entries: list[dict]) -> int:
    seconds = 0
    for entry in entries:
        rx = entry["prescription"]
        seconds += rx["sets"] * (rx["rest_seconds"] + _SECONDS_PER_SET_OVERHEAD)
    return round(seconds / 60)


def _apply_week(day: dict, modifier: dict) -> dict:
    """Return a copy of a day with the week's volume/effort modifier applied."""
    exercises = []
    for entry in day["exercises"]:
        rx = dict(entry["prescription"])
        rx["sets"] = max(1, rx["sets"] + modifier["set_delta"])
        rx["rir"] = max(0, rx["rir"] + modifier["rir_delta"])
        rx["load_pct_of_baseline"] = modifier["load_pct"]
        exercises.append({**entry, "prescription": rx})
    return {**day, "exercises": exercises,
            "estimated_minutes": _estimate_minutes(exercises)}


def weekly_set_volume(day_list: list[dict]) -> dict[str, int]:
    """Hard sets per body part across a week — the number that drives results."""
    volume: dict[str, int] = {}
    for day in day_list:
        for entry in day["exercises"]:
            part = entry["exercise"]["body_part"]
            volume[part] = volume.get(part, 0) + entry["prescription"]["sets"]
    return dict(sorted(volume.items(), key=lambda kv: -kv[1]))


def generate(profile: Profile, catalog: Catalog | None = None) -> dict:
    """Generate a full mesocycle for ``profile``."""
    profile.validate()
    catalog = catalog or get_catalog()
    equipment = catalog.resolve_equipment(profile.equipment)
    rng = random.Random(profile.seed)

    split_name, days = select_split(profile.days_per_week, profile.level)
    used: set[str] = set()
    base_days = [_build_day(catalog, day, profile, equipment, used, rng)
                 for day in days]

    if not any(d["exercises"] for d in base_days):
        raise ValueError(
            "no exercises match the requested equipment — widen the equipment "
            "profile or reduce exclusions"
        )

    model = progression_model(profile.level)
    weeks = []
    for week in range(1, profile.weeks + 1):
        modifier = week_modifier(model, week, profile.weeks)
        week_days = [_apply_week(d, modifier) for d in base_days]
        weeks.append({
            "week": week,
            "is_deload": modifier["load_pct"] < 1.0,
            "guidance": modifier["note"],
            "days": week_days,
            "weekly_set_volume": weekly_set_volume(week_days),
        })

    return {
        "profile": {
            "goal": profile.goal,
            "level": profile.level,
            "days_per_week": profile.days_per_week,
            "equipment": profile.equipment,
            "session_minutes": profile.session_minutes,
            "weeks": profile.weeks,
            "language": profile.language,
        },
        "split": split_name,
        "progression_model": model,
        "weeks": weeks,
        "attribution": "© Gym visual — https://gymvisual.com/",
    }
