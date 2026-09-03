"""HTTP API over the exercise catalog and the program engine.

Run locally:

    pip install -r requirements.txt
    uvicorn api.main:app --reload

Every response that carries media paths also carries the Gym visual
attribution required by ``NOTICE.md``; clients must keep it visible.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine.catalog import EQUIPMENT_PROFILES, get_catalog
from engine.prescription import GOALS, LEVELS
from engine.programs import Profile, generate

ATTRIBUTION = "© Gym visual — https://gymvisual.com/"

app = FastAPI(
    title="Exercises API",
    version="1.0.0",
    description=(
        "1,324 exercises with media and 9-language instructions, plus a "
        "training-program generator. Media " + ATTRIBUTION
    ),
)


# --- tiering ----------------------------------------------------------
# Keys are read from the environment so the free tier works out of the box
# and a deployment can gate the program endpoint without a database:
#   EXERCISES_API_KEYS="key1:pro,key2:free"
def _load_keys() -> dict[str, str]:
    raw = os.environ.get("EXERCISES_API_KEYS", "").strip()
    keys = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        key, _, tier = item.partition(":")
        keys[key.strip()] = (tier or "free").strip()
    return keys


API_KEYS = _load_keys()
REQUIRE_KEY = os.environ.get("EXERCISES_REQUIRE_KEY", "").lower() in {"1", "true"}


def tier(x_api_key: str | None = Header(default=None)) -> str:
    """Resolve the caller's tier from their API key."""
    if not API_KEYS and not REQUIRE_KEY:
        return "pro"  # unconfigured deployment: everything open, for local dev
    if x_api_key in API_KEYS:
        return API_KEYS[x_api_key]
    if REQUIRE_KEY:
        raise HTTPException(status_code=401, detail="valid X-API-Key required")
    return "free"


def require_pro(caller_tier: str = Depends(tier)) -> str:
    if caller_tier != "pro":
        raise HTTPException(
            status_code=402,
            detail="program generation requires a pro API key",
        )
    return caller_tier


# --- models -----------------------------------------------------------
class ProgramRequest(BaseModel):
    goal: Literal[GOALS] = "hypertrophy"  # type: ignore[valid-type]
    level: Literal[LEVELS] = "beginner"  # type: ignore[valid-type]
    days_per_week: int = Field(3, ge=2, le=6)
    equipment: str | list[str] = "full_gym"
    session_minutes: int = Field(60, ge=20, le=180)
    weeks: int = Field(4, ge=1, le=12)
    language: str = "en"
    seed: int | None = None
    exclude_patterns: list[str] = Field(default_factory=list)


# --- routes -----------------------------------------------------------
@app.get("/v1/health")
def health() -> dict:
    catalog = get_catalog()
    return {"status": "ok", "exercises": len(catalog.exercises)}


@app.get("/v1/facets")
def facets() -> dict:
    """Every value that can be filtered on — clients build their UI from this."""
    return get_catalog().facets()


@app.get("/v1/exercises")
def list_exercises(
    pattern: str | None = None,
    role: str | None = None,
    mechanic: str | None = None,
    body_part: str | None = None,
    target: str | None = None,
    difficulty: str | None = None,
    equipment_profile: str | None = None,
    q: str | None = Query(default=None, description="substring match on name"),
    language: str = "en",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    caller_tier: str = Depends(tier),
) -> JSONResponse:
    catalog = get_catalog()
    try:
        equipment = catalog.resolve_equipment(equipment_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = catalog.find(
        pattern=pattern, role=role, mechanic=mechanic, body_part=body_part,
        target=target, equipment=equipment, query=q, max_difficulty=difficulty,
    )
    page = results[offset:offset + limit]
    return JSONResponse({
        "total": len(results),
        "limit": limit,
        "offset": offset,
        "attribution": ATTRIBUTION,
        "results": [_serialize(e, language) for e in page],
    })


@app.get("/v1/exercises/{exercise_id}")
def get_exercise(exercise_id: str, language: str = "en",
                 caller_tier: str = Depends(tier)) -> dict:
    exercise = get_catalog().by_id.get(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="exercise not found")
    return {"attribution": ATTRIBUTION, **_serialize(exercise, language)}


@app.post("/v1/programs")
def create_program(request: ProgramRequest,
                   caller_tier: str = Depends(require_pro)) -> dict:
    profile = Profile(
        goal=request.goal,
        level=request.level,
        days_per_week=request.days_per_week,
        equipment=request.equipment,
        session_minutes=request.session_minutes,
        weeks=request.weeks,
        language=request.language,
        seed=request.seed,
        exclude_patterns=tuple(request.exclude_patterns),
    )
    try:
        return generate(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _serialize(exercise: dict, language: str) -> dict:
    """Trim a record to one language so responses stay small."""
    instructions = exercise.get("instructions") or {}
    steps = exercise.get("instruction_steps") or {}
    lang = language if language in instructions else "en"
    return {
        "id": exercise["id"],
        "name": exercise["name"],
        "body_part": exercise["body_part"],
        "target": exercise["target"],
        "equipment": exercise["equipment"],
        "muscle_group": exercise.get("muscle_group"),
        "secondary_muscles": exercise.get("secondary_muscles"),
        "pattern": exercise["pattern"],
        "mechanic": exercise["mechanic"],
        "role": exercise["role"],
        "difficulty": exercise["difficulty"],
        "image": exercise["image"],
        "gif_url": exercise["gif_url"],
        "language": lang,
        "instructions": instructions.get(lang),
        "instruction_steps": steps.get(lang) or steps.get("en") or [],
    }
