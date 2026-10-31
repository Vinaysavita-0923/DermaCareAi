"""
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/logout

See README.md for request/response examples and how to try these from
/docs.
"""
from __future__ import annotations

import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    InvalidTokenError,
    bearer_scheme,
    create_access_token,
    authenticate_user,
    decode_access_token,
    get_current_user,
    hash_password,
)
from app.database.connection import get_db
from app.database.models import RevokedToken, User
from app.schemas.auth_schema import MessageResponse, TokenResponse, UserCreate, UserLogin, UserOut

logger = logging.getLogger("skincare_api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        # Same wording style as login's generic error — still don't
        # want to be overly specific about account state here, but
        # "already registered" is unavoidable to say for a working
        # signup flow (the alternative is a confusing silent failure).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Covers a race: two near-simultaneous registrations with the
        # same email both pass the check above before either commits.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    db.refresh(user)
    logger.info("New user registered (id=%s)", user.id)  # never log email/password
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        # Deliberately identical whether the email doesn't exist, the
        # password is wrong, or the account is inactive.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token, expires_at = create_access_token(user_id=user.id)
    logger.info("User logged in (id=%s)", user.id)  # never log the token or password
    return TokenResponse(access_token=token, expires_at=expires_at, user=user)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Logout records this specific token's `jti` as revoked until its
    natural expiry. See README for why this is necessary for a
    stateless JWT, and its limitations (other tokens for the same user,
    e.g. on another device, are unaffected — by design, that's a
    separate login session)."""
    # get_current_user (above) already rejected the request with 401 if
    # there were no credentials, so this is always real at this point —
    # the assert documents that instead of silently trusting it.
    assert credentials is not None
    payload = decode_access_token(credentials.credentials)
    jti = payload["jti"]
    expires_at = datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.timezone.utc)

    if db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
        db.commit()

    logger.info("User logged out (id=%s)", current_user.id)
    return MessageResponse(message="Logged out successfully.")
