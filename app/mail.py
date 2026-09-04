"""Outbound email, behind a swappable backend.

No provider is wired up yet — that is a deliberate gap, not an oversight.
Choosing one means an account, a bill and a verified sending domain, so the
decision belongs to whoever runs the deployment. Everything above this file is
finished and tested; picking a provider means implementing one class here and
naming it in ``EMAIL_BACKEND``.

Until then the console backend prints what *would* have been sent, so the
reset flow is fully exercisable in development.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    """What a provider has to implement."""

    def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleSender:
    """Logs the message instead of sending it. The development default.

    Logged at warning level, not info: this backend exists so a developer can
    read the link, and the common server defaults — uvicorn's included — hide
    info from anything but their own loggers, which would make the one useful
    line invisible. An email that was not actually delivered is a warning in
    any case.
    """

    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.warning("EMAIL (not sent — no provider configured)\n"
                       "  to:      %s\n  subject: %s\n  body:\n%s",
                       to, subject, body)


class NullSender:
    """Drops the message silently.

    For test runs and for a deployment that has deliberately turned the
    feature off; the endpoints still behave correctly, they just never
    deliver.
    """

    def send(self, *, to: str, subject: str, body: str) -> None:
        return None


_BACKENDS: dict[str, type] = {
    "console": ConsoleSender,
    "null": NullSender,
}


def get_sender() -> EmailSender:
    """The configured backend, from ``EMAIL_BACKEND`` (default: console)."""
    name = os.environ.get("EMAIL_BACKEND", "console").strip().lower()
    backend = _BACKENDS.get(name)
    if backend is None:
        raise ValueError(
            f"unknown EMAIL_BACKEND {name!r}; available: {sorted(_BACKENDS)}"
        )
    return backend()


def email_is_deliverable() -> bool:
    """Whether a real provider is configured.

    The reset endpoint uses this only to log a warning; it never changes what
    the caller is told, because that would leak which addresses have accounts.
    """
    return os.environ.get("EMAIL_BACKEND", "console").strip().lower() not in {
        "console", "null",
    }


def password_reset_message(reset_url: str, ttl_minutes: int) -> tuple[str, str]:
    """Subject and body for the reset email."""
    subject = "Reset your training account password"
    body = (
        "Someone asked to reset the password for this account.\n\n"
        f"Open this link to choose a new one:\n{reset_url}\n\n"
        f"The link works once and expires in {ttl_minutes} minutes.\n\n"
        "If this was not you, nothing has changed and you can ignore this "
        "message."
    )
    return subject, body
