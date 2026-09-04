"""In-memory catalog over ``data/exercises.json``.

Loads the dataset once, annotates every record with the movement taxonomy, and
indexes it so program generation and the API can filter without rescanning
1,324 records per request.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from functools import lru_cache

from .taxonomy import DIFFICULTY_RANK, annotate

DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "exercises.json",
)

# Equipment the dataset lists, grouped into the profiles people actually train
# in. A request says "home_dumbbell"; the catalog expands it to real values.
EQUIPMENT_PROFILES: dict[str, set[str]] = {
    "bodyweight": {"body weight"},
    "home_minimal": {"body weight", "band", "resistance band", "stability ball"},
    "home_dumbbell": {
        "body weight", "dumbbell", "band", "resistance band", "stability ball",
        "kettlebell", "weighted", "roller", "wheel roller", "medicine ball",
    },
    "full_gym": set(),  # empty == no restriction
}


# Equipment ranked by how well it serves a main lift. Anything unlisted scores
# 0, so a barbell bench press outranks an obscure machine variation.
EQUIPMENT_SCORE = {
    "barbell": 6, "olympic barbell": 6, "trap bar": 5, "dumbbell": 5,
    "body weight": 4, "kettlebell": 4, "ez barbell": 4, "cable": 3,
    "leverage machine": 3, "smith machine": 2, "weighted": 2, "band": 2,
    "resistance band": 1, "assisted": 1,
}

# The dataset carries many near-duplicate variations; these markers flag the
# ones that are variants of a canonical lift rather than the lift itself.
VARIANT_MARKERS = ("v. 2", "v. 3", "v. 4", "(male)", "(female)", "version")


def quality_score(exercise: dict) -> float:
    """How canonical an exercise is, independent of any particular slot.

    Used wherever a list of candidates has to be ranked for a human — filling
    a program slot, or offering a substitute — so that "barbell squat" comes
    ahead of "dumbbell biceps curl squat".
    """
    score = float(EQUIPMENT_SCORE.get(exercise["equipment"], 0))
    name = exercise["name"].lower()
    if any(marker in name for marker in VARIANT_MARKERS):
        score -= 3
    # Long names are almost always heavily-qualified variations.
    score -= len(name.split()) * 0.5
    return score


class Catalog:
    """Queryable view over the annotated exercise dataset."""

    def __init__(self, exercises: list[dict]):
        self.exercises = [annotate(e) for e in exercises]
        self.by_id = {e["id"]: e for e in self.exercises}
        self._by_pattern: dict[str, list[dict]] = defaultdict(list)
        self._by_equipment: dict[str, list[dict]] = defaultdict(list)
        for e in self.exercises:
            self._by_pattern[e["pattern"]].append(e)
            self._by_equipment[e["equipment"]].append(e)

    # -- construction ----------------------------------------------------
    @classmethod
    def load(cls, path: str | None = None) -> "Catalog":
        with open(path or DEFAULT_DATA_PATH, encoding="utf-8") as fh:
            return cls(json.load(fh))

    # -- queries ---------------------------------------------------------
    def resolve_equipment(self, profile_or_list) -> set[str] | None:
        """Turn a profile name or explicit list into a set of equipment values.

        Returns ``None`` for "no restriction".
        """
        if profile_or_list is None:
            return None
        if isinstance(profile_or_list, str):
            allowed = EQUIPMENT_PROFILES.get(profile_or_list)
            if allowed is None:
                raise ValueError(f"unknown equipment profile: {profile_or_list}")
            return allowed or None
        allowed = set(profile_or_list)
        return allowed or None

    def find(
        self,
        *,
        pattern: str | None = None,
        role: str | None = None,
        mechanic: str | None = None,
        body_part: str | None = None,
        target: str | None = None,
        equipment: set[str] | None = None,
        exclude_ids: set[str] | None = None,
        query: str | None = None,
        max_difficulty: str | None = None,
    ) -> list[dict]:
        """Filter the catalog. All criteria are ANDed; ``None`` means "any"."""
        pool = self._by_pattern[pattern] if pattern else self.exercises
        exclude_ids = exclude_ids or set()
        needle = query.lower() if query else None
        ceiling = (DIFFICULTY_RANK[max_difficulty]
                   if max_difficulty is not None else None)
        out = []
        for e in pool:
            if ceiling is not None and DIFFICULTY_RANK[e["difficulty"]] > ceiling:
                continue
            if role and e["role"] != role:
                continue
            if mechanic and e["mechanic"] != mechanic:
                continue
            if body_part and e["body_part"] != body_part:
                continue
            if target and e["target"] != target:
                continue
            if equipment is not None and e["equipment"] not in equipment:
                continue
            if e["id"] in exclude_ids:
                continue
            if needle and needle not in e["name"].lower():
                continue
            out.append(e)
        return out

    def facets(self) -> dict[str, list[str]]:
        """Distinct values available for filtering — useful for API discovery."""
        def distinct(key):
            return sorted({e[key] for e in self.exercises if e.get(key)})
        return {
            "pattern": distinct("pattern"),
            "role": distinct("role"),
            "mechanic": distinct("mechanic"),
            "difficulty": distinct("difficulty"),
            "body_part": distinct("body_part"),
            "target": distinct("target"),
            "equipment": distinct("equipment"),
            "equipment_profile": sorted(EQUIPMENT_PROFILES),
        }


@lru_cache(maxsize=1)
def get_catalog(path: str | None = None) -> Catalog:
    """Process-wide cached catalog."""
    return Catalog.load(path)
