"""
POST /api/v1/acne/analyze  — upload a face/skin image for (experimental)
                             acne analysis.

Authenticated. The uploaded image is validated and decoded in memory,
used only for this request, and never written to disk or persisted. The
response never includes a filesystem path or stored-image reference.

While no verified model checkpoint is configured, this endpoint returns
a clear "model_not_configured" status and makes NO prediction — it does
not fabricate a class or a confidence score.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.security import get_current_user
from app.database.models import User
from app.schemas.acne_schema import AcneAnalysisResponse
from app.services.acne_service import ImageValidationError, analyze_image

logger = logging.getLogger("skincare_api.acne")
settings = get_settings()

router = APIRouter(prefix="/acne", tags=["acne"])


@router.post("/analyze", response_model=AcneAnalysisResponse)
async def analyze_acne_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> AcneAnalysisResponse:
    # Read with a hard byte cap so an oversized upload can't exhaust
    # memory before the size check runs. Read one byte past the limit so
    # we can tell "exactly at limit" from "over limit".
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
        # 422: the upload was received fine but isn't a usable image.
        raise HTTPException(status_code=422, detail=exc.message)
    except NotImplementedError:
        # A checkpoint path is set but real inference isn't wired yet.
        # Honest 503 rather than a fabricated answer.
        logger.warning("Acne checkpoint configured but inference not implemented.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Acne analysis is not available yet.",
        )
    finally:
        # Be explicit about not holding the upload open.
        await image.close()

    # Log only that an analysis happened and its status — never the
    # image, and never anything identifying.
    logger.info("Acne analyze: user=%s status=%s", current_user.id, result.model_status)

    return AcneAnalysisResponse(
        model_status=result.model_status,
        predicted_class=result.predicted_class,
        raw_score=result.raw_score,
        is_diagnosis=result.is_diagnosis,
        note=result.note,
    )
