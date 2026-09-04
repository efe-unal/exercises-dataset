"""Authentication dependencies and account operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .mail import (
    email_is_deliverable,
    get_sender,
    password_reset_message,
)
from .models import AuthToken, PasswordResetToken, User, utcnow
from .security import (
    RESET_TOKEN_TTL,
    TOKEN_TTL,
    WeakPassword,
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)

logger = logging.getLogger(__name__)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid email or password",
)


def register_user(session: Session, email: str, password: str,
                  display_name: str | None = None,
                  language: str = "en") -> User:
    email = normalize_email(email)
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="an account with this email already exists")
    try:
        password_hash = hash_password(password)
    except WeakPassword as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc
    user = User(email=email, password_hash=password_hash,
                display_name=display_name, language=language)
    session.add(user)
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    # Verify even when the user is missing, so a wrong email and a wrong
    # password take the same time and cannot be told apart.
    reference = user.password_hash if user else _DUMMY_HASH
    ok = verify_password(password, reference)
    if user is None or not ok:
        raise CREDENTIALS_ERROR
    return user


def issue_token(session: Session, user: User) -> tuple[str, datetime]:
    """Create a session token and return ``(token, expires_at)``."""
    token, token_hash = generate_token()
    expires_at = utcnow() + TOKEN_TTL
    session.add(AuthToken(user_id=user.id, token_hash=token_hash,
                          expires_at=expires_at))
    session.commit()
    return token, expires_at


def revoke_token(session: Session, token: str) -> None:
    row = session.scalar(
        select(AuthToken).where(AuthToken.token_hash == hash_token(token)))
    if row is not None:
        session.delete(row)
        session.commit()


def request_password_reset(session: Session, email: str,
                           reset_url_template: str) -> None:
    """Send a reset link, if that address has an account.

    Says nothing either way to the caller. Whether an email exists is exactly
    what an attacker probing for accounts wants to learn, so this succeeds
    identically for an unknown address.
    """
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        return

    # Any earlier link for this account stops working: two live reset links
    # is one more than anybody needs.
    for existing in session.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None))):
        session.delete(existing)

    token, token_hash = generate_token()
    session.add(PasswordResetToken(user_id=user.id, token_hash=token_hash,
                                   expires_at=utcnow() + RESET_TOKEN_TTL))
    session.commit()

    if not email_is_deliverable():
        logger.warning(
            "A password reset was requested but no email provider is "
            "configured, so nothing was delivered. Set EMAIL_BACKEND.",
        )
    subject, body = password_reset_message(
        reset_url_template.replace("{token}", token),
        int(RESET_TOKEN_TTL.total_seconds() // 60),
    )
    try:
        get_sender().send(to=user.email, subject=subject, body=body)
    except Exception:  # noqa: BLE001 - a provider outage must not 500 the caller
        logger.exception("Failed to send a password reset email")


def reset_password(session: Session, token: str, new_password: str) -> None:
    """Consume a reset token and set a new password.

    Every existing session is dropped: a password reset usually means the old
    one is compromised, and leaving other devices signed in would defeat the
    point.
    """
    row = session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token)))
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="this reset link is invalid or has expired",
    )
    if row is None or row.used_at is not None:
        raise invalid
    if _as_aware(row.expires_at) < utcnow():
        session.delete(row)
        session.commit()
        raise invalid

    try:
        password_hash = hash_password(new_password)
    except WeakPassword as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc

    user = session.get(User, row.user_id)
    if user is None:
        raise invalid
    user.password_hash = password_hash
    row.used_at = utcnow()

    for existing in session.scalars(
            select(AuthToken).where(AuthToken.user_id == user.id)):
        session.delete(existing)
    session.commit()


def _as_aware(moment: datetime) -> datetime:
    """SQLite hands back naive datetimes; compare them as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def current_user(authorization: str | None = Header(default=None),
                 session: Session = Depends(get_session)) -> User:
    """Resolve the caller from a ``Authorization: Bearer <token>`` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    row = session.scalar(
        select(AuthToken).where(AuthToken.token_hash == hash_token(token)))
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="invalid token")
    if _as_aware(row.expires_at) < utcnow():
        session.delete(row)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="token expired")
    row.last_used_at = utcnow()
    session.commit()
    return row.user


def require_pro(user: User = Depends(current_user)) -> User:
    if user.tier != "pro":
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="this feature requires a pro subscription")
    return user


# A real hash of a random password, used to keep failed logins constant-time.
_DUMMY_HASH = hash_password("not-a-real-password-placeholder")
