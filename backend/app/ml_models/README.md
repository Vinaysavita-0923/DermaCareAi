# ML models shipped with the backend

This folder holds the model files the backend actually loads at runtime.
It's the deployment target, not where models are trained — training lives
in [`../../../ml/`](../../../ml) (a separate, un-deployed folder; see
below). Nothing here is a medical diagnosis — see
[`skin_condition_service.py`](../services/skin_condition_service.py) and
[`acne_service.py`](../services/acne_service.py) for the full honesty/safety
rules this doc summarizes.

| File | Size | Used by | Status |
|---|---|---|---|
| `skin_gate.onnx` | 11.9 MB | `skin_condition_service.py` | **shipped, live** |
| `skin_condition_efficientnet_b0.onnx` | 16.1 MB | `skin_condition_service.py` | **shipped, live** |
| *(acne severity model)* | — | `acne_service.py` | **not shipped** — endpoint returns `model_not_configured` |

Both shipped files are plain **ONNX**, run with `onnxruntime` +
`numpy` only (CPU, no PyTorch/TensorFlow at runtime — see
[`requirements.txt`](../../requirements.txt)) so the backend stays light
enough for a free host.

## How they're wired together

`POST /api/v1/skin-condition/analyze` (in
[`api/skin_condition.py`](../api/skin_condition.py)) runs both models in
sequence, in `skin_condition_service.analyze_image()`:

1. **Gate first** — `skin_gate.onnx` scores P(this is a real photo of
   skin). Below `_MIN_SKIN_PROB = 0.5`, the request stops here with
   `not_skin: true` and **no prediction is made**. This exists because the
   22-class model below always picks *some* class — a meme used to come
   back "Normal / Healthy Skin 84%" before the gate was added.
2. **Classifier second** — only if the gate passes, `skin_condition_efficientnet_b0.onnx`
   returns the top-k guesses out of its 22 classes.

`POST /api/v1/acne/analyze` (in [`api/acne.py`](../api/acne.py)) has no
model file to load yet and always returns `model_status:
"model_not_configured"` — it never fabricates a class or score. See
[`../../../ml/acne_model/README.md`](../../../ml/acne_model/README.md)
for the training package meant to produce that checkpoint.

## `skin_gate.onnx` — skin vs. not-skin

- **Architecture:** ImageNet MobileNetV3-Large backbone (frozen) +
  logistic-regression head, folded into one graph (Linear + Sigmoid) and
  exported as a single ONNX file.
- **Input:** `(1, 3, 224, 224)` float32, RGB, resized to 224×224,
  ImageNet-normalized (mean `[0.485, 0.456, 0.406]`, std
  `[0.229, 0.224, 0.225]`) — see `_to_tensor()` in
  `skin_condition_service.py`.
- **Output:** a single float, P(skin), 0–1.
- **Decision rule:** reject (no analysis) if P(skin) < 0.5.
- **Held-out accuracy:** 99.74%. Full training data sources, licensing
  caveats, and benchmark numbers: [`../../../ml/skin_gate/README.md`](../../../ml/skin_gate/README.md).
  Retrain with `python ml/skin_gate/train_gate.py`.

## `skin_condition_efficientnet_b0.onnx` — 22-class skin-condition classifier

- **Architecture:** EfficientNet-B0, fine-tuned (PyTorch), exported to ONNX.
- **Input:** `(1, 3, 300, 300)` float32, RGB, resized to 300×300,
  same ImageNet normalization as the gate.
- **Output:** `(1, 22)` logits — softmax is applied in
  `skin_condition_service.py`, not inside the graph.
- **Classes (training order, ImageFolder-sorted):** Acne, Actinic
  Keratosis, Benign Tumour, Bullous Disease, Candidiasis, Drug Eruption,
  Eczema, Infestation / Bites, Lichen Planus, Lupus, Moles, Psoriasis,
  Rosacea, Seborrhoeic Keratosis, Skin Cancer, Sun / Sunlight Damage,
  Tinea (Fungal Infection), Normal / Healthy Skin, Vascular Tumour,
  Vasculitis, Vitiligo, Warts. The full label → serious-flag → product
  "concern" tag mapping lives in `CLASSES` in `skin_condition_service.py`
  — update both together if the class order ever changes.
- **Thresholds applied after inference:**
  - `_LOW_CONFIDENCE = 0.40` — below this top-1 score, the result is
    reported as "uncertain" rather than a named condition.
  - `_SERIOUS_FLOOR = 0.15` — a "serious" class (e.g. Skin Cancer, Lupus,
    Bullous Disease) only triggers the see-a-doctor note at this score or
    higher, or if it's the top guess, so a trace prediction doesn't scare
    the user over a confident harmless result.
- **Reported accuracy:** ~75% top-1 on the source project's held-out web
  images; expect lower on real phone photos, which is why results are
  always labelled experimental and never a diagnosis.
- **Provenance:** trained outside this repo on the Kaggle
  ["Skin Disease Dataset"](https://www.kaggle.com/datasets/pacificrm/skindiseasedataset)
  (13,898 train / 1,546 test images) using EfficientNet-B0 transfer
  learning (AdamW, cosine annealing, label smoothing, class weights).
  Full training details, per-class precision/recall, and the original
  Streamlit demo: [`../../../Skin-Disease-Detection-main/`](../../../Skin-Disease-Detection-main/Skin-Disease-Detection-main/README.md).
  **There is no training/retraining code for this model inside
  `skincare-ai-final/`** — only the exported `.onnx` file is vendored
  here. Retraining means working in that source project and re-exporting
  to ONNX, then swapping this file (see "Replacing a model" below).

## Loading, config, and failure behaviour

`_load_session()` / `_load_gate()` in `skin_condition_service.py`
(`@lru_cache`, loaded once per process) resolve each model path as:

1. `settings.skin_condition_model_path` / `settings.skin_gate_model_path`
   (env vars, see [`core/config.py`](../core/config.py)) if set, else
2. the bundled default in this folder.

If a file is missing, unreadable, or fails to load, `_open_onnx()` logs a
warning and returns `None` instead of raising — the endpoint then answers
`model_status: "model_not_configured"`. **No model ever fails silently
into a fabricated prediction**; see the module docstrings in
`skin_condition_service.py` / `acne_service.py` for the full honesty
contract this project holds itself to.

## Replacing a model

1. Export the new model to ONNX with a single `(1, 3, H, W)` float32
   input and the output shape this service expects (`(1,1)` sigmoid for
   the gate, `(1, N)` logits for the classifier).
2. Drop it in this folder under the same filename, **or** point
   `SKIN_GATE_MODEL_PATH` / `SKIN_CONDITION_MODEL_PATH` at it via env var
   — no code change needed for a drop-in replacement with the same input
   size, preprocessing, and class count/order.
3. If the input size, normalization, or class list changes, update the
   matching constants in `skin_condition_service.py` (`_INPUT_SIZE`,
   `_GATE_INPUT_SIZE`, `_MEAN`/`_STD`, `CLASSES`) — these are **not**
   read from the ONNX file.
4. Re-run `backend/tests/test_skin_condition.py` and spot-check a few
   real photos before shipping.
