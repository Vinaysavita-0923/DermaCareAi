"""
POST /api/v1/skin-condition/analyze — upload a skin photo for an
experimental 22-class skin-condition check.

Authenticated. The image is validated and decoded in memory, used only
for this request, and never written to disk or persisted. The response
never includes a filesystem path or stored-image reference, and is never
a medical diagnosis.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.security import get_current_user
from app.database.models import User
from app.schemas.skin_condition_schema import ConditionGuess, SkinConditionResponse
from app.services.acne_service import ImageValidationError
from app.services.skin_condition_service import analyze_image

logger = logging.getLogger("skincare_api.skin_condition")
settings = get_settings()

router = APIRouter(prefix="/skin-condition", tags=["skin-condition"])


@router.post("/analyze", response_model=SkinConditionResponse)
async def analyze_skin_condition(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> SkinConditionResponse:
    # Same hard byte cap as the acne endpoint, so an oversized upload
    # can't exhaust memory before the size check runs.
    max_bytes = int(settings.acne_max_image_mb * 1024 * 1024)
    raw = await image.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image is too large. Maximum size is {settings.acne_max_image_mb:.0f} MB.",
        )

    try:
        result = analyze_image(raw)
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    finally:
        await image.close()

    logger.info(
        "Skin-condition analyze: user=%s status=%s top=%s",
        current_user.id,
        result.model_status,
        result.predictions[0].label if result.predictions else None,
    )

    return SkinConditionResponse(
        model_status=result.model_status,
        predictions=[
            ConditionGuess(label=g.label, score=g.score, serious=g.serious, concern=g.concern)
            for g in result.predictions
        ],
        low_confidence=result.low_confidence,
        any_serious=result.any_serious,
        is_diagnosis=result.is_diagnosis,
        note=result.note,
        not_skin=result.not_skin,
    )
