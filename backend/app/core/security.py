"""
Everything authentication-related that isn't a route:
  * password hashing/verification (Argon2, via pwdlib)
  * password strength validation
  * JWT access tokens (create + decode)
  * the reusable `get_current_user` dependency every protected route uses
  * `ensure_owner`, the one place "does this record belong to this
    user" is checked, so that rule is never reimplemented ad hoc

Nothing in this file ever logs a password, a token, or a password hash.
"""
from __future__ import annotations

import datetime
import re
import uuid
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import get_db
from app.database.models import RevokedToken, User

settings = get_settings()
_password_hasher = PasswordHash.recommended()  # Argon2id, with sane defaults

# A reusable "dummy" hash, computed once, used only to burn roughly the
# same amount of time as a real password check when the email wasn't
# found at all — see authenticate_user() below. The password behind it
# is never used anywhere.
_DUMMY_HASH = _password_hasher.hash("not-a-real-password-just-for-timing")

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hasher.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------
# Password strength
# ---------------------------------------------------------------------
# Deliberately simple and clearly documented, rather than a long list of
# fiddly rules: at least 8 characters, at least one letter, at least one
# digit. This is enforced in the Pydantic schema (schemas/auth_schema.py)
# via this function, so the same rule can't drift between two places.
def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    return password


# ---------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------
def create_access_token(*, user_id: int) -> tuple[str, datetime.datetime]:
    """Returns (token, expires_at). Every token gets a random `jti` so
    it can be individually revoked on logout, independent of every
    other token the same user may hold (e.g. on another device)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


class InvalidTokenError(Exception):
    """Raised for any token problem — expired, malformed, wrong
    signature, or revoked. Deliberately one exception type so callers
    can't accidentally treat one failure mode as more trustworthy than
    another."""


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Token is invalid.") from exc
    return payload


# ---------------------------------------------------------------------
# Login helper — timing-safe-ish against email enumeration
# ---------------------------------------------------------------------
def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Returns the User on success, or None on any failure. Deliberately
    gives the caller no way to distinguish "no such email" from "wrong
    password" — the route layer turns None into one generic error
    message either way, per the project brief."""
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.hashed_password:
        # Still run a hash comparison against a dummy hash so this path
        # takes roughly as long as the real one — a basic defense against
        # timing-based email enumeration. Not a complete guarantee, but a
        # meaningful improvement over returning instantly.
        _password_hasher.verify(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


# ---------------------------------------------------------------------
# The reusable auth dependency every protected route will use
# ---------------------------------------------------------------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Protects a route: raises 401 if there's no token, the token is
    invalid/expired, the token was revoked (logged out), or the user no
    longer exists/is inactive. On success, returns the real User row —
    this, and only this, is where "who is making this request" comes
    from. Route handlers must never accept a user id as a request
    parameter and trust it instead."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise unauthorized

    jti = payload.get("jti")
    if jti and db.get(RevokedToken, jti) is not None:
        raise unauthorized

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized

    return user


def ensure_owner(resource_user_id: int, current_user: User) -> None:
    """The one place "does this record belong to this user" is checked.
    Every Phase 4+ endpoint that loads a profile, journal entry, chat
    session, routine, or report must call this before returning or
    modifying it — never compare against a user id taken from the
    request itself.

    Raises 404, not 403: confirming that a record exists at all (even
    to say "you can't see it") leaks information about other users'
    data, so a resource that isn't yours looks identical to one that
    doesn't exist.
    """
    if resource_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
