"""Account endpoints: register, log in, log out, read and update the profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import authenticate, current_user, issue_token, register_user, revoke_token
from ..db import get_session
from ..models import User
from ..schemas import (
    LoginRequest,
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
