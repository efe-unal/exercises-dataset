"""HTTP API: the exercise catalog, the program engine, and the app backend.

Run locally:

    pip install -r requirements.txt
    uvicorn api.main:app --reload      # docs at http://127.0.0.1:8000/docs

The surface splits in two:

* **Catalog** (``/v1/exercises``, ``/v1/facets``, ``/v1/programs/preview``) —
  stateless, optionally gated by an API key. This is the developer-facing
  product.
* **App backend** (``/v1/auth``, ``/v1/programs``, ``/v1/workouts``) — accounts,
  saved programs and workout logging, authenticated with a bearer token. This
  is what the web and mobile clients talk to.

Every response carrying media paths also carries the Gym visual attribution
required by ``NOTICE.md``; clients must keep it visible.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import create_all
from app.routers import accounts, programs, workouts
from engine.catalog import get_catalog, quality_score

from .ratelimit import RateLimitMiddleware

ATTRIBUTION = "© Gym visual — https://gymvisual.com/"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_all()
    get_catalog()  # warm the catalog so the first request is not slow
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Exercises API",
    version="2.0.0",
    description=(
        "1,324 exercises with media and 9-language instructions, a training-"
        "program generator, and the account, program and workout-logging "
        "backend behind the web and mobile clients. Media " + ATTRIBUTION
    ),
)


# --- middleware -------------------------------------------------------
# The web client and the installed PWA are served from a different origin than
# the API, so browsers need explicit permission. Set ALLOWED_ORIGINS to the
# real front-end origins in production; the default is permissive for local
# development only.
_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins == "*" else
                  [o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


# --- API-key tiering for the catalog ----------------------------------
# Keys come from the environment so a deployment needs no database:
#   EXERCISES_API_KEYS="key1:pro,key2:free"
def _load_keys() -> dict[str, str]:
    raw = os.environ.get("EXERCISES_API_KEYS", "").strip()
    keys = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        key, _, tier_name = item.partition(":")
        keys[key.strip()] = (tier_name or "free").strip()
    return keys


API_KEYS = _load_keys()
REQUIRE_KEY = os.environ.get("EXERCISES_REQUIRE_KEY", "").lower() in {"1", "true"}


def tier(x_api_key: str | None = Header(default=None)) -> str:
    """Resolve an API caller's tier. Unconfigured deployments stay open."""
    if not API_KEYS and not REQUIRE_KEY:
        return "pro"
    if x_api_key in API_KEYS:
        return API_KEYS[x_api_key]
    if REQUIRE_KEY:
        raise HTTPException(status_code=401, detail="valid X-API-Key required")
    return "free"


# --- catalog routes ---------------------------------------------------
@app.get("/v1/health", tags=["catalog"])
def health() -> dict:
    return {"status": "ok", "exercises": len(get_catalog().exercises),
            "version": app.version}


@app.get("/v1/facets", tags=["catalog"])
def facets() -> dict:
    """Every value that can be filtered on — clients build their UI from this."""
    return get_catalog().facets()


@app.get("/v1/exercises", tags=["catalog"])
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


@app.get("/v1/exercises/{exercise_id}", tags=["catalog"])
def get_exercise(exercise_id: str, language: str = "en",
                 caller_tier: str = Depends(tier)) -> dict:
    exercise = get_catalog().by_id.get(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="exercise not found")
    return {"attribution": ATTRIBUTION, **_serialize(exercise, language)}


@app.get("/v1/exercises/{exercise_id}/alternatives", tags=["catalog"])
def alternatives(
    exercise_id: str,
    equipment_profile: str | None = None,
    difficulty: str | None = None,
    language: str = "en",
    limit: int = Query(8, ge=1, le=50),
    caller_tier: str = Depends(tier),
) -> dict:
    """Movements that can stand in for this one.

    The rack is busy, the machine is taken, a joint is complaining — the
    athlete needs a substitute now, and it has to train the same thing. The
    movement taxonomy is what makes this answerable: same pattern and same
    mechanic means the same job in the session, which a shared muscle name
    does not.
    """
    catalog = get_catalog()
    original = catalog.by_id.get(exercise_id)
    if original is None:
        raise HTTPException(status_code=404, detail="exercise not found")
    try:
        equipment = catalog.resolve_equipment(equipment_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    candidates = catalog.find(
        pattern=original["pattern"], mechanic=original["mechanic"],
        equipment=equipment, exclude_ids={exercise_id},
        max_difficulty=difficulty or original["difficulty"],
    )
    # Rank by: a different piece of equipment first, since a substitute on
    # the same machine does not help when that machine is the problem; then
    # the same role, so a main lift is replaced by a main lift; then how
    # canonical the movement is.
    candidates.sort(key=lambda e: (
        e["equipment"] == original["equipment"],
        e["role"] != original["role"],
        -quality_score(e),
    ))

    return {
        "exercise_id": exercise_id,
        "pattern": original["pattern"],
        "mechanic": original["mechanic"],
        "attribution": ATTRIBUTION,
        "alternatives": [_serialize(e, language) for e in candidates[:limit]],
    }


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


# --- app backend ------------------------------------------------------
app.include_router(accounts.router)
app.include_router(programs.router)
app.include_router(workouts.router)


# --- media ------------------------------------------------------------
# Served from the repository so a client can render a GIF straight from the
# `image` / `gif_url` path in any response. Behind a CDN in production, but
# correct as-is.
for _folder in ("images", "videos"):
    _path = os.path.join(REPO_ROOT, _folder)
    if os.path.isdir(_path):
        app.mount(f"/{_folder}", StaticFiles(directory=_path), name=_folder)
