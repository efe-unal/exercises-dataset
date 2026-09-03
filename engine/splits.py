"""Session templates — which movement patterns a training day is made of.

A slot lists candidate patterns in preference order; the generator takes the
first one it can fill from the athlete's available equipment, so a template
degrades gracefully instead of failing when someone has no barbell.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    patterns: tuple[str, ...]   # candidates, best first
    role: str                   # primary | accessory | mobility
    label: str                  # human-readable slot name


@dataclass(frozen=True)
class Day:
    name: str
    slots: tuple[Slot, ...]


def _s(label, role, *patterns) -> Slot:
    return Slot(patterns=tuple(patterns), role=role, label=label)


FULL_BODY_A = Day("Full body A", (
    _s("Squat pattern", "primary", "squat", "lunge"),
    _s("Horizontal push", "primary", "horizontal_push"),
    _s("Horizontal pull", "primary", "horizontal_pull", "vertical_pull"),
    _s("Hip hinge", "accessory", "hinge"),
    _s("Core", "accessory", "core"),
))

FULL_BODY_B = Day("Full body B", (
    _s("Hip hinge", "primary", "hinge", "squat"),
    _s("Vertical push", "primary", "vertical_push", "horizontal_push"),
    _s("Vertical pull", "primary", "vertical_pull", "horizontal_pull"),
    _s("Single-leg", "accessory", "lunge", "squat"),
    _s("Core", "accessory", "core"),
))

FULL_BODY_C = Day("Full body C", (
    _s("Squat pattern", "primary", "squat"),
    _s("Horizontal push", "primary", "horizontal_push"),
    _s("Vertical pull", "primary", "vertical_pull", "horizontal_pull"),
    _s("Shoulder isolation", "accessory", "shoulder_isolation"),
    _s("Arms", "accessory", "elbow_flexion", "elbow_extension"),
    _s("Core", "accessory", "core"),
))

UPPER = Day("Upper body", (
    _s("Horizontal push", "primary", "horizontal_push"),
    _s("Horizontal pull", "primary", "horizontal_pull"),
    _s("Vertical push", "primary", "vertical_push"),
    _s("Vertical pull", "primary", "vertical_pull"),
    _s("Shoulder isolation", "accessory", "shoulder_isolation"),
    _s("Elbow flexion", "accessory", "elbow_flexion"),
    _s("Elbow extension", "accessory", "elbow_extension"),
))

LOWER = Day("Lower body", (
    _s("Squat pattern", "primary", "squat"),
    _s("Hip hinge", "primary", "hinge"),
    _s("Single-leg", "accessory", "lunge"),
    _s("Posterior chain", "accessory", "hinge"),
    _s("Calves", "accessory", "calf"),
    _s("Core", "accessory", "core"),
))

PUSH = Day("Push", (
    _s("Horizontal push", "primary", "horizontal_push"),
    _s("Vertical push", "primary", "vertical_push"),
    _s("Chest accessory", "accessory", "horizontal_push"),
    _s("Shoulder isolation", "accessory", "shoulder_isolation"),
    _s("Elbow extension", "accessory", "elbow_extension"),
    _s("Core", "accessory", "core"),
))

PULL = Day("Pull", (
    _s("Vertical pull", "primary", "vertical_pull"),
    _s("Horizontal pull", "primary", "horizontal_pull"),
    _s("Back accessory", "accessory", "horizontal_pull"),
    _s("Rear delts / traps", "accessory", "shoulder_isolation"),
    _s("Elbow flexion", "accessory", "elbow_flexion"),
    _s("Grip / forearms", "accessory", "forearm"),
))

LEGS = Day("Legs", (
    _s("Squat pattern", "primary", "squat"),
    _s("Hip hinge", "primary", "hinge"),
    _s("Single-leg", "accessory", "lunge"),
    _s("Quad accessory", "accessory", "squat"),
    _s("Calves", "accessory", "calf"),
    _s("Core", "accessory", "core"),
))

# days_per_week -> (split name, ordered days)
SPLITS: dict[int, tuple[str, tuple[Day, ...]]] = {
    2: ("Full body 2x", (FULL_BODY_A, FULL_BODY_B)),
    3: ("Full body 3x", (FULL_BODY_A, FULL_BODY_B, FULL_BODY_C)),
    4: ("Upper / Lower", (UPPER, LOWER, UPPER, LOWER)),
    5: ("Push / Pull / Legs + Upper / Lower", (PUSH, PULL, LEGS, UPPER, LOWER)),
    6: ("Push / Pull / Legs 2x", (PUSH, PULL, LEGS, PUSH, PULL, LEGS)),
}

# Beginners are better served by full-body frequency than by a body-part split,
# even when they want to train 4-5 days.
BEGINNER_SPLITS: dict[int, tuple[str, tuple[Day, ...]]] = {
    4: ("Full body 3x + upper", (FULL_BODY_A, FULL_BODY_B, FULL_BODY_C, UPPER)),
    5: ("Full body 3x + upper / lower", (FULL_BODY_A, FULL_BODY_B, FULL_BODY_C,
                                         UPPER, LOWER)),
    6: ("Upper / Lower 3x", (UPPER, LOWER, UPPER, LOWER, UPPER, LOWER)),
}


def select_split(days_per_week: int, level: str) -> tuple[str, tuple[Day, ...]]:
    if days_per_week not in SPLITS:
        raise ValueError("days_per_week must be between 2 and 6")
    if level == "beginner" and days_per_week in BEGINNER_SPLITS:
        return BEGINNER_SPLITS[days_per_week]
    return SPLITS[days_per_week]
