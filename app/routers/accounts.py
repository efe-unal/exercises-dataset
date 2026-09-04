"""Account endpoints: register, log in, log out, read and update the profile."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import (
    authenticate,
    current_user,
    issue_token,
    register_user,
    request_password_reset,
    reset_password,
    revoke_token,
)
from ..db import get_session
from ..models import User
from ..schemas import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["accounts"])


@router.post("/register", response_model=TokenResponse,
             status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest,
             session: Session = Depends(get_session)) -> TokenResponse:
    user = register_user(session, request.email, request.password,
                         request.display_name, request.language)
    token, expires_at = issue_token(session, user)
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest,
          session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate(session, request.email, request.password)
    token, expires_at = issue_token(session, user)
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: str | None = Header(default=None),
           session: Session = Depends(get_session),
           user: User = Depends(current_user)) -> None:
    # current_user has already validated the header shape.
    revoke_token(session, authorization.split(" ", 1)[1].strip())


# Where the reset link points. The app owns the page that takes a new
# password, so the API only needs to know how to address it.
RESET_URL_TEMPLATE = os.environ.get(
    "PASSWORD_RESET_URL", "http://localhost:5173/reset-password?token={token}")


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_reset(request: PasswordResetRequest,
                  session: Session = Depends(get_session)) -> dict:
    """Ask for a reset link.

    Always reports the same thing, whether or not that address has an account:
    telling the caller which emails are registered is exactly the answer an
    attacker is looking for.
    """
    request_password_reset(session, request.email, RESET_URL_TEMPLATE)
    return {"detail": "If that address has an account, a reset link is on its "
                      "way."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_reset(request: PasswordResetConfirm,
                  session: Session = Depends(get_session)) -> None:
    """Set a new password using a reset link, and sign every device out."""
    reset_password(session, request.token, request.password)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(request: UpdateUserRequest,
              session: Session = Depends(get_session),
              user: User = Depends(current_user)) -> User:
    changes = request.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="no fields to update")
    for field, value in changes.items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    return user
