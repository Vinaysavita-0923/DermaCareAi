"""
POST /api/v1/assessment         - save a NEW assessment (always appends
                                   a history snapshot; also upserts the
                                   live SkinProfile every other feature
                                   reads from)
GET  /api/v1/assessment/me      - the current live profile (extended
                                   shape - same row as GET /profile)
PUT  /api/v1/assessment/me      - partial update of the live profile
                                   only (no new history row - see the
                                   POST/PUT distinction in the project
                                   brief: "save a new" vs "update")
GET  /api/v1/assessment/history - this user's past assessment snapshots,
                                   newest first
GET  /api/v1/assessment/profile - the personalized assessment engine's
                                   output (ingredient education)
GET  /api/v1/assessment/recommendations
                                 - the above PLUS product/routine
                                   recommendations (delegates to the
                                   existing recommendation_service -
                                   not a second product-matching system)

Ownership model matches /profile and /recommendations exactly: no
id in the URL, always the authenticated caller's own data.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import SkinAssessmentHistory, SkinProfile, User
from app.knowledge_base.skin_assessment_dataset import age_to_age_group, subtypes_for_skin_type
from app.schemas.profile_schema import (
    AssessmentHistoryOut,
    PersonalizedProfileOut,
    SkinProfileOut,
    SkinProfileUpdate,
)
from app.schemas.catalog_schema import RecommendationResponse
from app.services import assessment_service
from app.services.recommendation_service import NoProfileError, build_recommendations
from pydantic import BaseModel

router = APIRouter(prefix="/assessment", tags=["assessment"])


def _get_owned_profile(db: Session, user: User) -> SkinProfile | None:
    return db.query(SkinProfile).filter(SkinProfile.user_id == user.id).first()


def _apply_age_group(changes: dict) -> dict:
    """If age is being set, derive and store age_group alongside it -
    the dataset is keyed on age group, not raw age."""
    if "age" in changes and changes["age"] is not None:
        group, note = age_to_age_group(changes["age"])
        changes["age_group"] = group
        if note:
            changes["_age_group_note"] = note  # consumed by the caller, never persisted
    return changes


def _validate_subtype_against_saved_type(payload: SkinProfileUpdate, existing: SkinProfile | None) -> None:
    """SkinProfileUpdate already validates skin_type+skin_subtype
    against each other when BOTH are in the same request. This covers
    the other case: a request that changes only skin_subtype, checked
    against whatever skin_type is already saved (or about to be
    defaulted) for this user."""
    if payload.skin_subtype is None or payload.skin_type is not None:
        return
    current_type = existing.skin_type.value if existing else "unsure"
    if current_type == "unsure":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set a skin type before choosing a subtype.",
        )
    valid = subtypes_for_skin_type(current_type)
    if payload.skin_subtype not in valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{payload.skin_subtype}' is not a valid subtype for {current_type}. Valid options: {valid}",
        )


def _upsert_profile(db: Session, user: User, changes: dict) -> SkinProfile:
    profile = _get_owned_profile(db, user)
    if profile is None:
        profile = SkinProfile(user_id=user.id, **changes)
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            # Same race-recovery pattern as /profile's PUT.
            db.rollback()
            profile = _get_owned_profile(db, user)
            if profile is None:
                raise
            for field, value in changes.items():
                setattr(profile, field, value)
            db.commit()
    else:
        for field, value in changes.items():
            setattr(profile, field, value)
        db.commit()
    db.refresh(profile)
    return profile


class AssessmentCreateResponse(SkinProfileOut):
    history_id: int
    age_group_note: str | None = None


@router.post("", response_model=AssessmentCreateResponse, status_code=status.HTTP_201_CREATED)
def submit_assessment(
    payload: SkinProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentCreateResponse:
    """Saves a brand-new assessment: upserts the live profile AND
    appends an immutable row to the history table, so past answers are
    never lost even though the live profile is overwritten."""
    existing = _get_owned_profile(db, current_user)
    _validate_subtype_against_saved_type(payload, existing)

    changes = payload.model_dump(exclude_unset=True)
    full_name = changes.pop("full_name", None)
    changes = _apply_age_group(changes)
    note = changes.pop("_age_group_note", None)

    if full_name:
        current_user.full_name = full_name

    profile = _upsert_profile(db, current_user, changes)

    history = SkinAssessmentHistory(
        user_id=current_user.id,
        age=profile.age,
        age_group=profile.age_group,
        skin_type=profile.skin_type,
        skin_subtype=profile.skin_subtype,
        is_sensitive=profile.is_sensitive,
        concerns=profile.concerns,
        sensitivity_notes=profile.sensitivity_notes,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return AssessmentCreateResponse(
        **SkinProfileOut.model_validate(profile).model_dump(),
        history_id=history.id,
        age_group_note=note,
    )


@router.get("/me", response_model=SkinProfileOut)
def get_my_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkinProfile:
    profile = _get_owned_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No skin assessment yet. Use POST /assessment to create one.",
        )
    return profile


@router.put("/me", response_model=SkinProfileOut)
def update_my_assessment(
    payload: SkinProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkinProfile:
    """Partial update of the live profile only - does not add a new
    history row (that's what POST /assessment is for)."""
    existing = _get_owned_profile(db, current_user)
    _validate_subtype_against_saved_type(payload, existing)

    changes = payload.model_dump(exclude_unset=True)
    full_name = changes.pop("full_name", None)
    changes = _apply_age_group(changes)
    changes.pop("_age_group_note", None)

    if full_name:
        current_user.full_name = full_name

    return _upsert_profile(db, current_user, changes)


@router.get("/history", response_model=list[AssessmentHistoryOut])
def get_my_assessment_history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SkinAssessmentHistory]:
    return (
        db.query(SkinAssessmentHistory)
        .filter(SkinAssessmentHistory.user_id == current_user.id)
        .order_by(desc(SkinAssessmentHistory.created_at))
        .limit(limit)
        .all()
    )


@router.get("/profile", response_model=PersonalizedProfileOut)
def get_personalized_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalizedProfileOut:
    profile = _get_owned_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save your skin assessment first to get a personalized profile.",
        )
    return assessment_service.build_personalized_profile(profile)


class AssessmentRecommendationsOut(BaseModel):
    personalized_profile: PersonalizedProfileOut
    products: RecommendationResponse


@router.get("/recommendations", response_model=AssessmentRecommendationsOut)
def get_assessment_recommendations(
    pregnant_or_trying: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentRecommendationsOut:
    profile = _get_owned_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save your skin assessment first to get recommendations.",
        )
    try:
        products = build_recommendations(db, current_user, pregnant_or_trying)
    except NoProfileError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Save your skin assessment first.")
    return AssessmentRecommendationsOut(
        personalized_profile=assessment_service.build_personalized_profile(profile),
        products=products,
    )
