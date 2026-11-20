"""
Experimental skin-condition image classifier.

A fine-tuned EfficientNet-B0 (PyTorch, trained on the Kaggle
"Skin Disease Dataset", 22 classes) exported to ONNX and run here with
onnxruntime — a small, CPU-only dependency that fits a free host, unlike
the full PyTorch/TensorFlow stacks.

HONESTY / SAFETY (matches acne_service.py and the project brief):
  * This is NEVER a diagnosis. The model's reported Top-1 accuracy is
    ~75% on its own held-out test set of web images; on real phone
    photos it will be lower. We surface the top few guesses with
    calibrated-looking softmax scores, clearly labelled as experimental.
  * If no model file is configured/loadable, we return an explicit
    "model_not_configured" status and make NO prediction.
  * "Serious" classes (possible skin cancer, lupus, etc.) always carry a
    see-a-doctor message and never a reassuring word.
  * If the top score is low, we say the result is uncertain instead of
    asserting a condition.

PRIVACY: the uploaded image is decoded in memory, classified, and
discarded. Nothing is written to disk and no path is ever returned.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.services.acne_service import validate_and_decode_image

logger = logging.getLogger("skincare_api.skin_condition")
settings = get_settings()

# The model's 22 output classes, in training order (ImageFolder sorted).
# Each carries a human label, whether it's a serious flag (-> always urge
# a clinician, never reassure), and an optional profile concern tag the
# rest of the app understands (so Kashvi / product search can follow up
# for the everyday, non-serious conditions only).
@dataclass(frozen=True)
class ConditionInfo:
    label: str
    serious: bool
    concern: str | None  # a DATASET concern tag, or None
    blurb: str


CLASSES: tuple[ConditionInfo, ...] = (
    ConditionInfo("Acne", False, "acne", "Clogged pores and breakouts; very common and manageable."),
    ConditionInfo("Actinic Keratosis", True, None, "Rough, sun-damaged patches that a doctor should check."),
    ConditionInfo("Benign Tumour", False, None, "A non-cancerous skin growth; have new or changing lumps checked."),
    ConditionInfo("Bullous Disease", True, None, "Blistering skin conditions that need medical care."),
    ConditionInfo("Candidiasis", True, None, "A yeast (fungal) skin infection; usually needs treatment."),
    ConditionInfo("Drug Eruption", True, None, "A skin reaction to a medicine; can be serious — seek advice."),
    ConditionInfo("Eczema", False, None, "Dry, itchy, inflamed skin; gentle, barrier-supporting care helps."),
    ConditionInfo("Infestation / Bites", False, None, "Insect bites or mites causing itchy marks."),
    ConditionInfo("Lichen Planus", True, None, "An inflammatory condition of skin or mouth; see a clinician."),
    ConditionInfo("Lupus", True, None, "Possible autoimmune skin involvement; needs a doctor."),
    ConditionInfo("Moles", False, None, "Pigmented spots; watch for change in size, colour or shape."),
    ConditionInfo("Psoriasis", False, None, "Thick, scaly plaques from fast skin-cell turnover."),
    ConditionInfo("Rosacea", False, "redness", "Facial redness and flushing; look for gentle, calming care."),
    ConditionInfo("Seborrhoeic Keratosis", False, None, "A common, harmless waxy growth; confirm with a clinician."),
    ConditionInfo("Skin Cancer", True, None, "Possible skin cancer — please see a doctor or dermatologist promptly."),
    ConditionInfo("Sun / Sunlight Damage", False, None, "Photo-ageing from UV; daily sunscreen is the priority."),
    ConditionInfo("Tinea (Fungal Infection)", True, None, "A ringworm-type fungal infection; usually needs antifungal treatment."),
    ConditionInfo("Normal / Healthy Skin", False, None, "No specific condition stood out to the model."),
    ConditionInfo("Vascular Tumour", True, None, "A blood-vessel growth that a doctor should assess."),
    ConditionInfo("Vasculitis", True, None, "Inflamed blood vessels; can be serious — seek care."),
    ConditionInfo("Vitiligo", False, None, "Loss of skin pigment in patches; harmless but worth a check."),
    ConditionInfo("Warts", False, None, "Harmless growths caused by a virus."),
)

_INPUT_SIZE = 300
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# Below this top-1 softmax score we treat the result as uncertain rather
# than asserting any single condition.
_LOW_CONFIDENCE = 0.40
# A serious guess only drives the "see a doctor" message when it scores at
# least this much, so a trace 0.5% serious class doesn't scare the user
# when the model is really confident about something harmless.
_SERIOUS_FLOOR = 0.15
# The classifier is forced to pick one of its 22 classes, so it returns a
# confident-looking label even for a photo that isn't skin at all (a meme, a
# street scene, a screenshot). A separate learned gate — an ImageNet backbone
# with a skin-vs-not-skin head, trained on faces, phone photos of skin
# conditions and clinical close-ups vs. objects, scenes and cartoons — runs
# first; below this P(skin) we make no prediction.
_GATE_INPUT_SIZE = 224
_MIN_SKIN_PROB = 0.5


@dataclass
class ConditionGuess:
    label: str
    score: float      # softmax score 0..1 (NOT a validated probability)
    serious: bool
    concern: str | None


@dataclass
class SkinConditionResult:
    model_status: str                 # "ok" | "model_not_configured"
    predictions: list[ConditionGuess]  # top guesses, best first (empty if no model / not skin)
    low_confidence: bool
    any_serious: bool
    is_diagnosis: bool                # always False
    note: str
    not_skin: bool = False            # True when the image doesn't look like skin


_ML_MODELS = Path(__file__).resolve().parent.parent / "ml_models"


def _open_onnx(path: Path, what: str):
    """Load an ONNX model, or return None (not an error) if the file or
    onnxruntime isn't available, so the endpoint can report an honest
    not-configured status instead of crashing."""
    if not path.is_file():
        logger.warning("%s model file not found at %s", what, path)
        return None
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        if len(session.get_outputs()[0].shape) != 2:
            raise ValueError("Unexpected model output shape.")
        return session
    except Exception:  # import error, corrupt file, wrong format…
        logger.exception("Could not load the %s ONNX model.", what)
        return None


@lru_cache(maxsize=1)
def _load_session():
    """The 22-class classifier: the configured path, or the bundled default."""
    configured = settings.skin_condition_model_path
    path = Path(configured) if configured else _ML_MODELS / "skin_condition_efficientnet_b0.onnx"
    return _open_onnx(path, "Skin-condition")


@lru_cache(maxsize=1)
def _load_gate():
    """The skin-vs-not-skin gate: the configured path, or the bundled default."""
    configured = settings.skin_gate_model_path
    path = Path(configured) if configured else _ML_MODELS / "skin_gate.onnx"
    return _open_onnx(path, "Skin gate")


def _to_tensor(image, size: int) -> np.ndarray:
    """PIL RGB image -> NCHW, ImageNet-normalised float tensor at size x size."""
    arr = np.asarray(image.resize((size, size)), dtype=np.float32)
    arr = (arr / 255.0 - _MEAN) / _STD
    return arr.transpose(2, 0, 1)[np.newaxis, :]  # (1, 3, H, W)


def _skin_probability(gate, image) -> float:
    tensor = _to_tensor(image, _GATE_INPUT_SIZE)
    return float(gate.run(None, {gate.get_inputs()[0].name: tensor})[0].ravel()[0])


def analyze_image(raw_bytes: bytes, top_k: int = 3) -> SkinConditionResult:
    """Validate the image and, if the model is available, return the top
    guesses. Never fabricates a result when no model is loaded."""
    # Validate first, so a bad upload is reported the same way either way.
    image = validate_and_decode_image(raw_bytes).convert("RGB")
    session, gate = _load_session(), _load_gate()
    if session is None or gate is None:
        # Without the gate we'd be classifying unchecked images — same as no model.
        return SkinConditionResult(
            model_status="model_not_configured",
            predictions=[],
            low_confidence=False,
            any_serious=False,
            is_diagnosis=False,
            note=(
                "The skin-condition model isn't available right now, so no "
                "analysis was made. This feature is experimental and is never "
                "a medical diagnosis."
            ),
        )

    # Guard: if the gate doesn't see real skin, don't hand back a confident
    # label for a meme or a street photo.
    if _skin_probability(gate, image) < _MIN_SKIN_PROB:
        return SkinConditionResult(
            model_status="ok",
            predictions=[],
            low_confidence=False,
            any_serious=False,
            is_diagnosis=False,
            not_skin=True,
            note=(
                "This doesn't look like a clear photo of skin, so no analysis was "
                "made. Please upload a close-up, well-lit photo of the skin area."
            ),
        )

    tensor = _to_tensor(image, _INPUT_SIZE)
    logits = session.run(None, {session.get_inputs()[0].name: tensor})[0][0]
    exp = np.exp(logits - logits.max())
    probs = exp / exp.sum()

    order = probs.argsort()[::-1][:top_k]
    guesses = [
        ConditionGuess(
            label=CLASSES[i].label,
            score=float(probs[i]),
            serious=CLASSES[i].serious,
            concern=CLASSES[i].concern,
        )
        for i in order
    ]
    top = guesses[0]
    low = top.score < _LOW_CONFIDENCE
    # Serious only "counts" for the warning if it's the top guess or scores
    # above the floor — a trace serious class shouldn't dominate the note.
    any_serious = top.serious or any(g.serious and g.score >= _SERIOUS_FLOOR for g in guesses)

    if low:
        note = (
            "The model isn't confident about this image. Treat the guesses "
            "below as rough only, and try a clearer, well-lit, close-up photo. "
            "This is experimental and never a diagnosis."
        )
    elif any_serious:
        note = (
            "One or more of these guesses can be serious. This tool is "
            "experimental and NOT a diagnosis — please have this looked at by "
            "a doctor or dermatologist."
        )
    else:
        note = (
            "Experimental result — not a medical diagnosis. If anything is "
            "painful, spreading, or not improving, see a doctor."
        )

    return SkinConditionResult(
        model_status="ok",
        predictions=guesses,
        low_confidence=low,
        any_serious=any_serious,
        is_diagnosis=False,
        note=note,
    )
