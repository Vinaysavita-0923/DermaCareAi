"""
Acne image-analysis service.

CURRENT STATE: no verified trained checkpoint exists in this
repository (searched: no .pt/.pth/.ckpt/.onnx/.safetensors, no model
config, no class map, no training/eval code). Per the project brief,
this service therefore:

  * validates and safely decodes uploaded images (this works and is
    tested regardless of whether a model exists),
  * returns an explicit "model_not_configured" status instead of ANY
    prediction — no fabricated class, no simulated confidence score,
  * is written so that when a real checkpoint is later verified, only
    `_load_model()` and `_run_inference()` need to be filled in; the
    validation, privacy, and API layers around them already work.

PRIVACY: uploaded images are held in memory only, validated, and
discarded. Nothing is written to disk and no prediction is persisted by
default. No filesystem path is ever returned to the client.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

logger = logging.getLogger("skincare_api.acne")
settings = get_settings()

# Pillow format names we accept. We rely on actually decoding the image
# (below), not on the client-supplied filename or content-type, to
# decide if it's a real image.
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_MAX_BYTES = int(settings.acne_max_image_mb * 1024 * 1024)
# Guard against decompression-bomb images regardless of byte size.
Image.MAX_IMAGE_PIXELS = 24_000_000  # ~24 MP ceiling


class ImageValidationError(Exception):
    """Raised for an upload we refuse: too big, not an image, or an
    unsupported image format. Carries a safe, user-facing message."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class AcneAnalysisResult:
    model_status: str            # "ok" | "model_not_configured"
    predicted_class: str | None
    raw_score: float | None
    is_diagnosis: bool           # always False — this is never a diagnosis
    note: str


def validate_and_decode_image(raw_bytes: bytes) -> Image.Image:
    """Validate size, then actually decode to confirm it's a real,
    supported image. Raises ImageValidationError on any problem. Never
    trusts the filename or declared content-type — only the decoded
    bytes."""
    if not raw_bytes:
        raise ImageValidationError("No image data was received.")
    if len(raw_bytes) > _MAX_BYTES:
        raise ImageValidationError(
            f"Image is too large. Maximum size is {settings.acne_max_image_mb:.0f} MB."
        )

    try:
        # verify() checks integrity without fully loading pixels...
        probe = Image.open(io.BytesIO(raw_bytes))
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageValidationError("The uploaded file is not a readable image.")

    # ...then we must re-open to actually use it (verify() leaves the
    # image unusable).
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageValidationError("The uploaded file could not be decoded as an image.")

    if image.format not in _ALLOWED_FORMATS:
        raise ImageValidationError(
            f"Unsupported image format '{image.format}'. "
            f"Please upload one of: {', '.join(sorted(_ALLOWED_FORMATS))}."
        )
    return image


def _checkpoint_available() -> bool:
    path = settings.acne_model_path
    if not path:
        return False
    return Path(path).is_file()


def analyze_image(raw_bytes: bytes) -> AcneAnalysisResult:
    """Validate the image, then either run real inference (if a verified
    checkpoint is configured) or return an honest not-configured result.
    Never returns a fabricated prediction.

    The image is decoded for validation and then goes out of scope here
    — it is never written to disk or persisted.
    """
    image = validate_and_decode_image(raw_bytes)  # raises on bad input

    if not _checkpoint_available():
        # The REQUIRED behavior while no verified model exists.
        return AcneAnalysisResult(
            model_status="model_not_configured",
            predicted_class=None,
            raw_score=None,
            is_diagnosis=False,
            note=(
                "No trained acne model is configured, so no prediction was "
                "made. This feature is experimental/research-only and, even "
                "once a model is added, will not be a medical diagnosis."
            ),
        )

    # --- Real inference path (only reached once a checkpoint exists) ---
    # Intentionally not implemented with guesses. When a verified
    # checkpoint is available, _load_model() and _run_inference() get
    # filled in to match THAT model's real architecture, input size,
    # preprocessing, and class map — none of which we may assume now.
    raise NotImplementedError(
        "A checkpoint path is configured but real inference is not yet "
        "implemented. Inference must be written against the verified "
        "checkpoint's actual architecture and class mapping — it must not "
        "be guessed. Refusing to fabricate a prediction."
    )
