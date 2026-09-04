"""Tests for the taxonomy, catalog and program engine."""

import pytest

from engine.catalog import get_catalog
from engine.prescription import LEVELS, GOALS, prescribe, week_modifier
from engine.programs import Profile, generate
from engine.taxonomy import DIFFICULTY_RANK, classify_difficulty, classify_pattern


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


# --- taxonomy ---------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("barbell bench press", "horizontal_push"),
    ("barbell deadlift", "hinge"),
    ("barbell full squat", "squat"),
    ("pull-up", "vertical_pull"),
    ("barbell bent over row", "horizontal_pull"),
    ("barbell shrug", "shoulder_isolation"),
    ("barbell upright row", "shoulder_isolation"),
    ("dumbbell biceps curl", "elbow_flexion"),
    ("chest dip (on dip-pull-up cage)", "horizontal_push"),
    ("standing calf raise", "calf"),
    ("assisted lying glutes stretch", "mobility"),
])
def test_pattern_classification(name, expected):
    assert classify_pattern({"name": name, "body_part": "chest"}) == expected


@pytest.mark.parametrize("name,expected", [
    ("push-up", "beginner"),
    ("pull-up", "intermediate"),
    ("muscle up", "advanced"),
    ("back lever", "advanced"),
    ("handstand push-up", "advanced"),
    ("dumbbell lateral raise", "beginner"),
])
def test_difficulty_classification(name, expected):
    assert classify_difficulty({"name": name}) == expected


def test_every_exercise_is_annotated(catalog):
    for exercise in catalog.exercises:
        assert exercise["pattern"]
        assert exercise["mechanic"] in {"compound", "isolation"}
        assert exercise["role"] in {"primary", "accessory", "mobility"}
        assert exercise["difficulty"] in DIFFICULTY_RANK


def test_every_pattern_has_at_least_one_exercise(catalog):
    for pattern in catalog.facets()["pattern"]:
        assert catalog.find(pattern=pattern)


# --- catalog ----------------------------------------------------------
def test_equipment_profile_restricts_results(catalog):
    equipment = catalog.resolve_equipment("bodyweight")
    results = catalog.find(equipment=equipment)
    assert results
    assert {e["equipment"] for e in results} == {"body weight"}


def test_full_gym_profile_is_unrestricted(catalog):
    assert catalog.resolve_equipment("full_gym") is None


def test_unknown_equipment_profile_raises(catalog):
    with pytest.raises(ValueError):
        catalog.resolve_equipment("space_station")


def test_max_difficulty_filters(catalog):
    for exercise in catalog.find(max_difficulty="beginner"):
        assert exercise["difficulty"] == "beginner"


# --- prescription -----------------------------------------------------
def test_strength_prescribes_lower_reps_than_endurance():
    strength = prescribe("strength", "intermediate", "primary", "compound")
    endurance = prescribe("endurance", "intermediate", "primary", "compound")
    assert strength.rep_max < endurance.rep_min
    assert strength.rest_seconds > endurance.rest_seconds


def test_isolation_never_gets_heavy_low_rep_sets():
    rx = prescribe("strength", "advanced", "accessory", "isolation")
    assert rx.rep_min >= 8


def test_beginners_train_further_from_failure():
    beginner = prescribe("hypertrophy", "beginner", "primary", "compound")
    advanced = prescribe("hypertrophy", "advanced", "primary", "compound")
    assert beginner.rir > advanced.rir
    assert beginner.sets < advanced.sets


def test_last_week_of_a_long_block_is_a_deload():
    assert week_modifier("double", 4, 4)["load_pct"] < 1.0
    assert week_modifier("double", 3, 4)["load_pct"] == 1.0
    # A short block has no room for a deload week.
    assert week_modifier("double", 3, 3)["load_pct"] == 1.0


# --- program generation -----------------------------------------------
def test_generates_requested_shape():
    program = generate(Profile(days_per_week=4, weeks=3, level="intermediate",
                               seed=1))
    assert len(program["weeks"]) == 3
    for week in program["weeks"]:
        assert len(week["days"]) == 4
        for day in week["days"]:
            assert day["exercises"]


def test_no_exercise_repeats_within_a_week():
    program = generate(Profile(days_per_week=6, level="intermediate", seed=1))
    ids = [entry["exercise"]["id"]
           for day in program["weeks"][0]["days"]
           for entry in day["exercises"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("level", LEVELS)
def test_never_prescribes_above_the_athletes_level(level):
    program = generate(Profile(level=level, days_per_week=3,
                               equipment="bodyweight", seed=2))
    for week in program["weeks"]:
        for day in week["days"]:
            for entry in day["exercises"]:
                assert (DIFFICULTY_RANK[entry["exercise"]["difficulty"]]
                        <= DIFFICULTY_RANK[level])


@pytest.mark.parametrize("minutes", [30, 45, 60, 90])
def test_sessions_respect_the_time_budget(minutes):
    program = generate(Profile(session_minutes=minutes, days_per_week=4,
                               level="intermediate", seed=4))
    for day in program["weeks"][0]["days"]:
        assert day["estimated_minutes"] <= minutes


@pytest.mark.parametrize("minutes,expected_cap", [
    (30, 3), (45, 4), (60, 6), (90, 8), (180, 8),
])
def test_sessions_never_run_to_a_dozen_movements(minutes, expected_cap):
    """Fitting in the time is not the same as being a sensible session."""
    program = generate(Profile(session_minutes=minutes, days_per_week=3,
                               level="beginner", seed=1))
    for day in program["weeks"][0]["days"]:
        assert len(day["exercises"]) <= expected_cap
        assert len(day["exercises"]) >= 3


def test_equipment_profile_is_honoured():
    program = generate(Profile(equipment="home_dumbbell", days_per_week=3,
                               seed=5))
    allowed = get_catalog().resolve_equipment("home_dumbbell")
    for day in program["weeks"][0]["days"]:
        for entry in day["exercises"]:
            assert entry["exercise"]["equipment"] in allowed


def test_seed_makes_generation_reproducible():
    a = generate(Profile(seed=42, days_per_week=3))
    b = generate(Profile(seed=42, days_per_week=3))
    assert a == b


def test_localized_instructions_are_returned():
    program = generate(Profile(language="tr", days_per_week=2, seed=6))
    entry = program["weeks"][0]["days"][0]["exercises"][0]
    assert entry["instructions"]["language"] == "tr"
    assert entry["instructions"]["steps"]


def test_unknown_language_falls_back_to_english():
    program = generate(Profile(language="xx", days_per_week=2, seed=6))
    entry = program["weeks"][0]["days"][0]["exercises"][0]
    assert entry["instructions"]["language"] == "en"


def test_media_attribution_is_present():
    program = generate(Profile(days_per_week=2, seed=6))
    assert "Gym visual" in program["attribution"]
    entry = program["weeks"][0]["days"][0]["exercises"][0]
    assert entry["exercise"]["attribution"]


@pytest.mark.parametrize("goal", GOALS)
def test_every_goal_generates(goal):
    program = generate(Profile(goal=goal, days_per_week=3, seed=8))
    assert program["weeks"][0]["weekly_set_volume"]


@pytest.mark.parametrize("kwargs", [
    {"goal": "bulking"},
    {"level": "elite"},
    {"days_per_week": 7},
    {"session_minutes": 5},
    {"weeks": 0},
])
def test_invalid_profiles_are_rejected(kwargs):
    with pytest.raises(ValueError):
        generate(Profile(**kwargs))


def test_excluding_a_pattern_removes_it_from_the_program():
    program = generate(Profile(days_per_week=4, level="intermediate",
                               exclude_patterns=("hinge",), seed=9))
    patterns = {entry["exercise"]["pattern"]
                for week in program["weeks"]
                for day in week["days"]
                for entry in day["exercises"]}
    assert "hinge" not in patterns
