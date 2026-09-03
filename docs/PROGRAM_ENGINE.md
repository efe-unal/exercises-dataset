# Program Engine

The dataset says *what* an exercise is. This engine says *what to do with it*:
given a goal, a training age, the equipment on hand and the time available, it
produces a full training block — split, exercise selection, sets, reps, rest,
effort and week-to-week progression.

```
data/exercises.json  ->  taxonomy  ->  catalog  ->  splits  ->  prescription  ->  program
   (1,324 records)      pattern /      indexed     session      sets / reps /      mesocycle
                        mechanic /     lookup      templates    rest / RIR
                        role /
                        difficulty
```

## Quick start

```bash
pip install -r requirements.txt

# a plan in the terminal
python -m engine.cli --goal hypertrophy --level intermediate \
    --days 4 --equipment home_dumbbell --minutes 60 --lang tr

# the same thing as JSON
python -m engine.cli --goal strength --level advanced --days 5 --json

# the HTTP API
uvicorn api.main:app --reload   # docs at http://127.0.0.1:8000/docs
```

```python
from engine import Profile, generate

program = generate(Profile(goal="hypertrophy", level="beginner",
                           days_per_week=3, equipment="home_dumbbell",
                           session_minutes=45, weeks=4, language="tr"))
```

## The derived layer

`engine/taxonomy.py` adds four fields the raw dataset does not carry. They are
what makes programmatic exercise selection possible:

| Field | Values | Why it exists |
| --- | --- | --- |
| `pattern` | `squat`, `hinge`, `lunge`, `horizontal_push`, `vertical_push`, `horizontal_pull`, `vertical_pull`, `elbow_flexion`, `elbow_extension`, `shoulder_isolation`, `core`, `calf`, `forearm`, `neck`, `carry`, `cardio`, `mobility` | A program is built from movement patterns, not from muscle names. |
| `mechanic` | `compound`, `isolation` | Decides set/rep ranges and session order. |
| `role` | `primary`, `accessory`, `mobility` | Only a free-weight compound should open a session. |
| `difficulty` | `beginner`, `intermediate`, `advanced` | A novice must never be handed a muscle-up. |

Classification is rule-based over the exercise name, with `body_part` as a
fallback. A pattern inferred from `body_part` alone is never promoted to
`primary` — the guess is not good enough to open a session with.

## How a program is built

1. **Split selection** (`engine/splits.py`) — `days_per_week` and `level` pick a
   template. Beginners get full-body frequency even at 4–5 days a week, because
   a body-part split wastes their recovery capacity.
2. **Slot filling** (`engine/programs.py`) — each slot lists candidate patterns
   in preference order, so a template degrades gracefully when the athlete has
   no barbell instead of failing. Candidates are scored (equipment quality,
   role match, penalties for near-duplicate variations) and drawn at random
   from the top band, so two generations differ without ever reaching for the
   worst option in the pool.
3. **Difficulty gate** — anything above the athlete's training age is filtered
   out entirely, not merely ranked down. A slot with no level-appropriate
   option is dropped.
4. **Time budget** — slots are added while the estimated session still fits
   `session_minutes`; the first three always stay. Leftover time is spent on
   accessory work for the day's own patterns.
5. **Prescription** (`engine/prescription.py`) — goal sets the base
   sets/reps/rest/tempo, role and level adjust it. Isolation work never gets
   heavy low-rep sets whatever the goal.
6. **Progression** — beginners get linear load, intermediates double
   progression, advanced lifters a volume wave. Blocks of four weeks or more
   end in a deload.

## Output

```jsonc
{
  "split": "Upper / Lower",
  "progression_model": "double",
  "weeks": [
    {
      "week": 1,
      "is_deload": false,
      "guidance": "Work reps up to the top of the range …",
      "days": [
        {
          "name": "Upper body",
          "estimated_minutes": 58,
          "exercises": [
            {
              "slot": "Horizontal push",
              "exercise": { "id": "0025", "name": "barbell bench press",
                            "pattern": "horizontal_push", "mechanic": "compound",
                            "role": "primary", "difficulty": "beginner",
                            "image": "images/…", "gif_url": "videos/…" },
              "instructions": { "language": "tr", "text": "…", "steps": ["…"] },
              "prescription": { "sets": 4, "rep_min": 8, "rep_max": 12,
                                "rest_seconds": 90, "rir": 1, "tempo": "3-0-1-0" },
              "load_step_kg": 2.5
            }
          ]
        }
      ],
      "weekly_set_volume": { "back": 27, "chest": 21, "…": 0 }
    }
  ],
  "attribution": "© Gym visual — https://gymvisual.com/"
}
```

`weekly_set_volume` counts hard sets per body part across the week — the number
that actually drives adaptation, and the one to check when judging whether a
generated plan is sane.

## API

| Endpoint | Tier | Purpose |
| --- | --- | --- |
| `GET /v1/health` | free | Liveness and record count. |
| `GET /v1/facets` | free | Every filterable value; build a client UI from it. |
| `GET /v1/exercises` | free | Filter, search and paginate; one language per response. |
| `GET /v1/exercises/{id}` | free | A single exercise. |
| `POST /v1/programs` | pro | Generate a block. |

Tiering is configured with environment variables, so a deployment needs no
database:

```bash
export EXERCISES_API_KEYS="somekey:free,otherkey:pro"
export EXERCISES_REQUIRE_KEY=1
```

Unconfigured, everything is open — convenient for local development, so set
both variables before exposing the API publicly.

## Media terms

The GIFs and thumbnails belong to Gym visual and are redistributed here under
separate written permission: **180×180 only**, attribution required. Every API
response and generated program carries the notice, and it must stay visible in
anything built on top. See [`NOTICE.md`](../NOTICE.md). The engine code and the
taxonomy/prescription rules in this directory are not encumbered by those
terms — only the media is.

## Tests

```bash
python -m pytest tests/ -q
```

Covers pattern and difficulty classification, catalog filtering, prescription
logic, and the generator's invariants: no repeated exercise within a week, no
movement above the athlete's level, sessions inside the time budget, equipment
respected, and reproducibility from a seed.
