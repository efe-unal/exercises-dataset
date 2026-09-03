"""Movement classification layer.

The raw dataset describes *what muscle* an exercise hits, but not *how it
moves* or *how hard it is to recover from*. Program design needs both, so this
module derives three properties from the name/body_part/target fields:

* ``pattern``   -- the movement pattern (squat, hinge, horizontal_push, ...)
* ``mechanic``  -- ``compound`` or ``isolation``
* ``role``      -- ``primary`` (heavy, goes first) / ``accessory`` / ``mobility``

Rules are ordered: the first matching rule wins, so specific phrases must be
listed before generic ones.
"""

from __future__ import annotations

import re

PATTERNS = (
    "squat",
    "hinge",
    "lunge",
    "horizontal_push",
    "vertical_push",
    "horizontal_pull",
    "vertical_pull",
    "elbow_flexion",
    "elbow_extension",
    "shoulder_isolation",
    "core",
    "calf",
    "forearm",
    "neck",
    "carry",
    "cardio",
    "mobility",
)

# (compiled regex over the lowercased name, pattern)
_NAME_RULES: list[tuple[str, str]] = [
    # --- mobility / stretching: must come first, a "hamstring stretch" is not a hinge
    (r"\bstretch|mobility|foam roll|roller\b", "mobility"),
    # --- carries
    (r"farmer|suitcase carry|waiter walk|overhead carry", "carry"),
    # --- lower body
    (r"calf|calve|soleus|toe raise", "calf"),
    (r"lunge|split squat|step-up|step up|bulgarian", "lunge"),
    (r"deadlift|good morning|hip thrust|glute bridge|back extension|"
     r"hyperextension|romanian|rdl|kettlebell swing|swing|pull through|"
     r"pull-through|hip extension|leg curl|kickback", "hinge"),
    (r"squat|leg press|hack|sissy|wall sit|leg extension", "squat"),
    # --- upper body pull (before push: "pull-up" contains no 'press').
    # "chest dip (on dip-pull-up cage)" names the equipment, not the movement.
    (r"chest dip|triceps dip", "horizontal_push"),
    (r"pull-?up|chin-?up|pulldown|pull-?down|lat pull", "vertical_pull"),
    # Shrugs and upright rows are shoulder work despite the name; they must be
    # matched before the generic row rule.
    (r"shrug|upright row", "shoulder_isolation"),
    (r"\brow\b|row(ing)?\b|face pull|rear delt|reverse fly|reverse peck", "horizontal_pull"),
    # --- upper body push
    (r"overhead press|shoulder press|military|arnold|push press|"
     r"handstand|pike push", "vertical_push"),
    (r"bench press|chest press|push-?up|dip\b|fly|flye|pec deck|"
     r"peck deck|chest|svend", "horizontal_push"),
    # --- arms
    (r"curl", "elbow_flexion"),
    (r"triceps|skull ?crusher|pushdown|push-?down|kickback|"
     r"extension.*(triceps|arm)|french press", "elbow_extension"),
    # --- shoulders isolation
    (r"lateral raise|front raise|side raise|delt raise|\braise\b", "shoulder_isolation"),
    # --- core
    (r"crunch|sit-?up|plank|leg raise|russian twist|ab |abdominal|"
     r"oblique|wood ?chop|hollow|dead ?bug|bird ?dog|rollout|"
     r"mountain climber|v-?up|windshield|toes to bar|knee raise", "core"),
    # --- forearms / grip
    (r"wrist|grip|finger|forearm", "forearm"),
    # --- neck
    (r"neck", "neck"),
    # --- cardio machines
    (r"treadmill|elliptical|stationary bike|cycle|ergometer|skierg|"
     r"stepmill|rope jump|jump rope|run\b|sprint|burpee", "cardio"),
]

_COMPILED = [(re.compile(rx), pat) for rx, pat in _NAME_RULES]

# Fall back on the dataset's own taxonomy when the name gives nothing away.
_BODY_PART_FALLBACK = {
    "chest": "horizontal_push",
    "back": "horizontal_pull",
    "shoulders": "shoulder_isolation",
    "upper arms": "elbow_flexion",
    "lower arms": "forearm",
    "upper legs": "squat",
    "lower legs": "calf",
    "waist": "core",
    "cardio": "cardio",
    "neck": "neck",
}

# Patterns that are multi-joint and therefore drive a session.
_COMPOUND_PATTERNS = {
    "squat",
    "hinge",
    "lunge",
    "horizontal_push",
    "vertical_push",
    "horizontal_pull",
    "vertical_pull",
    "carry",
}

# Names that look compound by pattern but are single-joint machine work.
_ISOLATION_OVERRIDES = re.compile(
    r"fly|flye|pec deck|peck deck|leg extension|leg curl|"
    r"back extension|hyperextension|hip thrust|glute bridge|"
    r"kickback|pullover|rear delt|reverse fly|face pull|pull-?over"
)

# Equipment that cannot be loaded progressively in small jumps; used by the
# progression model, exposed here because it is a property of the movement.
FIXED_LOAD_EQUIPMENT = {"body weight", "assisted", "band", "resistance band"}


def classify_pattern(exercise: dict) -> str:
    """Return the movement pattern for one dataset record."""
    return _pattern_with_source(exercise)[0]


def _pattern_with_source(exercise: dict) -> tuple[str, str]:
    """Return ``(pattern, source)`` where source is ``name`` or ``fallback``.

    The source matters: a pattern guessed from ``body_part`` alone is not
    trustworthy enough to make an exercise the opening lift of a session.
    """
    name = (exercise.get("name") or "").lower()
    for rx, pattern in _COMPILED:
        if rx.search(name):
            return pattern, "name"
    return _BODY_PART_FALLBACK.get(exercise.get("body_part"), "core"), "fallback"


def classify_mechanic(exercise: dict, pattern: str | None = None) -> str:
    """Return ``compound`` or ``isolation``."""
    pattern = pattern or classify_pattern(exercise)
    name = (exercise.get("name") or "").lower()
    if _ISOLATION_OVERRIDES.search(name):
        return "isolation"
    return "compound" if pattern in _COMPOUND_PATTERNS else "isolation"


def classify_role(exercise: dict, pattern: str | None = None,
                  mechanic: str | None = None) -> str:
    """Return ``primary``, ``accessory`` or ``mobility``."""
    pattern = pattern or classify_pattern(exercise)
    if pattern == "mobility":
        return "mobility"
    mechanic = mechanic or classify_mechanic(exercise, pattern)
    if mechanic != "compound":
        return "accessory"
    if _pattern_with_source(exercise)[1] == "fallback":
        # Pattern was inferred from body_part only — keep it out of the
        # primary slot rather than opening a session with a guess.
        return "accessory"
    # Free-weight and bodyweight compounds carry a session; machine versions
    # are good work but are not what a program should open with.
    equipment = exercise.get("equipment")
    if equipment in {"barbell", "olympic barbell", "trap bar", "ez barbell",
                     "dumbbell", "kettlebell", "body weight", "weighted"}:
        return "primary"
    return "accessory"


DIFFICULTIES = ("beginner", "intermediate", "advanced")
DIFFICULTY_RANK = {name: i for i, name in enumerate(DIFFICULTIES)}

# Skill-dependent movements that a novice cannot perform, whatever their goal.
_ADVANCED = re.compile(
    r"back lever|front lever|planche|muscle[ -]?up|human flag|iron cross|"
    r"l[ -]?sit|l[ -]?pull|pistol|one[ -]arm push|one[ -]?arm pull|"
    r"one[ -]arm chin|handstand|korean dip|archer|snatch|clean and jerk|"
    r"jerk\b|depth jump|plyo|somersault|hanging leg raise|dragon flag|"
    r"behind neck|behind head|guillotine|sissy squat"
)

# Movements that need a base of strength or coordination but are learnable.
_INTERMEDIATE = re.compile(
    r"pull[ -]?up|chin[ -]?up|\bdip\b|\bdips\b|deadlift|front squat|"
    r"overhead squat|good morning|kettlebell swing|turkish|bulgarian|"
    r"jump squat|pike push|clean\b|power clean|romanian|hip thrust|nordic"
)


def classify_difficulty(exercise: dict) -> str:
    """Return ``beginner``, ``intermediate`` or ``advanced``."""
    name = (exercise.get("name") or "").lower()
    if _ADVANCED.search(name):
        return "advanced"
    if _INTERMEDIATE.search(name):
        return "intermediate"
    return "beginner"


def annotate(exercise: dict) -> dict:
    """Return the exercise with movement-taxonomy fields added."""
    pattern, _ = _pattern_with_source(exercise)
    mechanic = classify_mechanic(exercise, pattern)
    role = classify_role(exercise, pattern, mechanic)
    return {**exercise, "pattern": pattern, "mechanic": mechanic, "role": role,
            "difficulty": classify_difficulty(exercise)}
