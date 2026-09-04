"""A small in-process rate limiter.

Enough to stop one client from hammering the API or brute-forcing a password,
without adding Redis to a deployment that one person maintains. State lives in
the process, so with several workers the effective limit is the configured one
multiplied by the worker count — acceptable at this scale, and the point where
that stops being true is the point to move the counter into a shared store.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120"))
# Login and registration are guessing targets, so they get a much tighter
# budget than ordinary reads.
AUTH_LIMIT = int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "10"))
WINDOW_SECONDS = 60

_AUTH_PATHS = (
    "/v1/auth/login",
    "/v1/auth/register",
    # Reset requests are a way to probe for accounts and to spam an inbox, so
    # they get the same tight budget as a login.
    "/v1/auth/password-reset/request",
    "/v1/auth/password-reset/confirm",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = DEFAULT_LIMIT,
                 auth_limit: int = AUTH_LIMIT):
        super().__init__(app)
        self.limit = limit
        self.auth_limit = auth_limit
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        # Behind a proxy the socket address is the proxy's, so prefer the
        # forwarded header when one is present.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in {"/v1/health", "/docs", "/openapi.json"}:
            return await call_next(request)

        limit = self.auth_limit if path in _AUTH_PATHS else self.limit
        key = f"{self._client_key(request)}:{'auth' if limit == self.auth_limit else 'api'}"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = int(WINDOW_SECONDS - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        # Keep the table from growing without bound on a long-running process.
        if len(self._hits) > 10_000:
            self._prune(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(hits)))
        return response

    def _prune(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items()
                 if not hits or now - hits[-1] > WINDOW_SECONDS]
        for key in stale:
            del self._hits[key]
