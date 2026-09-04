# Running and deploying

Two processes: the API (Python) and the web app (static files). The API also
serves the exercise media, so a small deployment needs nothing else.

## Locally

```bash
# 1. the API
pip install -r requirements.txt
uvicorn api.main:app --reload          # http://127.0.0.1:8000, docs at /docs

# 2. the web app, in a second terminal
npm install
npm run dev                            # http://127.0.0.1:5173
```

The dev server proxies `/v1`, `/images` and `/videos` to the API, so the
browser stays on one origin and no CORS configuration is needed while
developing.

## Configuration

Copy `.env.example` to `.env` and edit it. Every setting is documented there;
these two matter most:

| Variable | Why it matters |
| --- | --- |
| `EXERCISES_API_KEYS` / `EXERCISES_REQUIRE_KEY` | **Unset, the catalog is open to everyone.** Set both before exposing the API publicly. |
| `ALLOWED_ORIGINS` | Browsers refuse cross-origin calls unless the API names the origins it trusts. `*` is development-only — it disables credentialed requests and lets any site call the API. |

`DATABASE_URL` defaults to a local SQLite file, which is enough for a single
server. Point it at Postgres (`postgresql+psycopg://…`) to scale out, or when
the host gives the container no persistent disk — a container that is replaced
takes an SQLite file with it.

## With Docker

```bash
docker build -t exercises-api .
docker run -p 8000:8000 --env-file .env \
  -v exercises-data:/srv/var \
  exercises-api
```

The image runs as a non-root user and keeps its database under `/srv/var`, so
mount a volume there or the data goes when the container does.

## Deploying the web app

```bash
VITE_API_URL=https://api.example.com npm run build --workspace web
```

`web/dist/` is then plain static files for any host. Two requirements:

- **Serve `index.html` for unknown paths.** A client-side router owns every
  URL, so `/progress` must return the app rather than a 404.
- **Serve it over HTTPS.** Service workers — and therefore installability and
  offline use — are disabled on plain HTTP everywhere but localhost.

Set `ALLOWED_ORIGINS` on the API to the origin you serve the app from.

## Schema changes

`create_all()` creates missing tables at startup, which is enough until the
first schema change that has to preserve live data. Introduce Alembic before
that point, not after.

## What is deliberately not here

- **Email delivery.** The password reset flow is complete and tested — tokens
  are single-use, expire in thirty minutes, invalidate the previous link, and
  sign every device out on success. What is missing is a provider to carry the
  message: `EMAIL_BACKEND=console` logs it instead of sending, so the flow
  works in development but a real user cannot recover their password. Turning
  it on means implementing one class in `app/mail.py` and naming it in
  `EMAIL_BACKEND`.
- **Payments.** Tiers are enforced (`user.tier`), but nothing sets a user to
  `pro` except an admin editing the row.
- **A shared rate-limit store.** The limiter counts per process, so with
  several workers the effective limit is multiplied by the worker count. Move
  the counter into Redis before that stops being acceptable.
