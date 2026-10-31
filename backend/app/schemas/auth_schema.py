"""
Request/response shapes for the auth endpoints.

UserOut is the important one from a security standpoint: it is the
*only* representation of a User that ever leaves the API. It has no
hashed_password field, so there is no way for a future route to
accidentally return one just by reusing this schema.
"""
from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.security import validate_password_strength


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty.")
        return value

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Never add hashed_password, google_sub, or anything else
    sensitive to this schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime.datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime.datetime
    user: UserOut


class MessageResponse(BaseModel):
    message: str
