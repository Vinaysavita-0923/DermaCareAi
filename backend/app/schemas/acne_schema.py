"""Response shape for the acne analysis endpoint.

There is no request body schema — the image arrives as a multipart file
upload, validated in the service layer, not as JSON.

This response never contains a filesystem path, a stored-image id, or
any raw model internals — only the honest status and (once a real model
exists) an experimental, clearly-non-diagnostic result.
"""
from __future__ import annotations

from pydantic import BaseModel


class AcneAnalysisResponse(BaseModel):
    model_status: str            # "ok" | "model_not_configured"
    predicted_class: str | None
    raw_score: float | None      # raw model score, NOT a calibrated probability
    is_diagnosis: bool           # always False
    note: str
