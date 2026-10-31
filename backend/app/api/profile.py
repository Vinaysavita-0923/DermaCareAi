"""
GET /api/v1/profile   — the current user's skin profile
PUT /api/v1/profile   — create it if absent, update it if present

Ownership model: there is no profile-id or user-id in the URL. The
profile acted on is *always* the one belonging to the authenticated
user (from get_current_user). There is simply no way, through this
API, to name someone else's profile — so cross-user access isn't
"prevented," it's structurally impossible.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import SkinProfile, User
from app.schemas.profile_schema import SkinProfileOut, SkinProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


def _get_owned_profile(db: Session, user: User) -> SkinProfile | None:
    return db.query(SkinProfile).filter(SkinProfile.user_id == user.id).first()


@router.get("", response_model=SkinProfileOut)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkinProfile:
    profile = _get_owned_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No skin profile yet. Use PUT /profile to create one.",
        )
    return profile


@router.put("", response_model=SkinProfileOut)
def upsert_my_profile(
    payload: SkinProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkinProfile:
    """Create the profile if the user doesn't have one, otherwise update
    it. Only the fields present in the request are changed; omitted
    fields keep their current values (partial update)."""
    profile = _get_owned_profile(db, current_user)
    # Only the fields the caller actually sent — so PUT with just
    # {"skin_type": "oily"} doesn't wipe out existing concerns.
    changes = payload.model_dump(exclude_unset=True)

    if profile is None:
        profile = SkinProfile(user_id=current_user.id, **changes)
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            # Race: two concurrent PUTs from the same user both saw "no
            # profile" and both tried to insert. The unique(user_id)
            # constraint stops the second. Recover by rolling back and
            # applying this request's changes to the row that won the
            # race, so the client still gets a correct 200 instead of a
            # 500. (Same recovery pattern as the register endpoint.)
            db.rollback()
            profile = _get_owned_profile(db, current_user)
            if profile is None:
                raise  # genuinely unexpected — let the global handler log it
            for field, value in changes.items():
                setattr(profile, field, value)
            db.commit()
    else:
        for field, value in changes.items():
            setattr(profile, field, value)
        db.commit()

    db.refresh(profile)
    return profile
