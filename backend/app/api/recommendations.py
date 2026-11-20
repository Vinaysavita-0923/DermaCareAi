"""
GET /api/v1/recommendations?pregnant_or_trying=false

Personalised product matches and a basic morning/evening routine from the
caller's own saved skin profile. Scoped to the caller (no id parameter).
Returns 404 with a clear message if no profile has been saved yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.schemas.catalog_schema import RecommendationResponse
from app.services.recommendation_service import NoProfileError, build_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationResponse)
def get_recommendations(
    pregnant_or_trying: bool = Query(
        default=False, description="Hide products with actives commonly avoided in pregnancy"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    try:
        return build_recommendations(db, current_user, pregnant_or_trying)
    except NoProfileError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Save your skin assessment first to get recommendations.",
        )
