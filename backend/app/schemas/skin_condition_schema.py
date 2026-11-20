"""Response shape for the experimental skin-condition endpoint.

No request body schema — the image arrives as a multipart file upload,
validated in the service layer. The response never contains a filesystem
path, a stored-image id, or raw model internals — only honest,
clearly-non-diagnostic guesses.
"""
from __future__ import annotations

from pydantic import BaseModel


class ConditionGuess(BaseModel):
    label: str
    score: float          # softmax score 0..1, NOT a validated probability
    serious: bool         # serious conditions always urge a clinician
    concern: str | None   # a profile concern tag to follow up on, or null


class SkinConditionResponse(BaseModel):
    model_status: str                  # "ok" | "model_not_configured"
    predictions: list[ConditionGuess]  # best first; empty when no model / not skin
    low_confidence: bool
    any_serious: bool
    is_diagnosis: bool                 # always False
    note: str
    not_skin: bool = False             # True when the image doesn't look like skin
