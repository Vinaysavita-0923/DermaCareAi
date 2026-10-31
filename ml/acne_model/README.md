# Acne Severity Model — Training & Evaluation Package

This is a **reproducible training package** for an acne-severity
classifier on the ACNE04 dataset. It is intentionally **separate** from
the backend (`../../backend`) and does not touch it.

> **Why this is a separate package you run yourself:** the environment
> this was authored in cannot reach the dataset host (HuggingFace) and
> has no GPU. So the real training must run where the data is reachable
> and a GPU is available — your Windows machine or Google Colab. This
> package is the complete, tested pipeline for doing that. It was
> smoke-tested end-to-end (inspect → train → evaluate → plots) on a tiny
> synthetic dataset to prove the code runs; **those synthetic artifacts
> were deleted and are not included.** No real metrics or checkpoint are
> claimed here — you produce them by running this on the real data.

## What it does

1. **Inspects** the real ACNE04 dataset and reports its actual
   structure, labels, class distribution, corrupt images, and exact
   duplicates — and **refuses to guess** if what it finds doesn't match
   the config.
2. **Trains** a transfer-learning classifier (ResNet18 by default,
   EfficientNet-B0 optional) with class-imbalance handling and
   leakage-aware splitting.
3. **Evaluates** on a held-out test split (never used for training or
   model selection) and writes real metrics + plots.
4. **Saves** everything the backend needs to use the model safely:
   checkpoint, class mapping, preprocessing config, training config.

## IMPORTANT: verify the dataset layout first (do not assume)

The ACNE04 directory structure and label scheme in `configs/default.yaml`
are **documented defaults, not verified against your copy.** ACNE04 is
most commonly distributed with a filename→severity-grade annotation file
and ~1,450 images graded on the Hayashi criterion into **4 severity
levels** — but you must confirm this against your actual download.

**Always run Step 1 (inspection) first.** It prints exactly what it
finds and stops with a clear message if the config is wrong. Fix the
config to match the report, then train.

## Setup

### Google Colab (recommended — free GPU, data reachable)

```python
# 1. Get the code (upload this ml/acne_model folder, or clone your repo)
%cd /content/acne_model

# 2. Dependencies (torch/torchvision are preinstalled on Colab)
!pip install -q scikit-learn matplotlib PyYAML Pillow

# 3. Get ACNE04 into ./data/ACNE04  (use YOUR dataset source; e.g. the
#    HuggingFace dataset you selected). Example with the datasets lib:
# !pip install -q datasets
# from datasets import load_dataset
# ds = load_dataset("Layered-Labs/ACNE04")   # then export images+labels to ./data/ACNE04
#    -> arrange as the inspection step expects, or set the config to match.

# 4. Inspect FIRST
!python inspect_dataset.py --config configs/default.yaml

# 5. Train, then evaluate
!python train.py --config configs/default.yaml
!python evaluate.py --config configs/default.yaml
```

Make sure the Colab runtime is **GPU** (Runtime → Change runtime type →
T4 GPU). Training on CPU works but is much slower.

### Windows (local — 8 GB RAM, MX350 2 GB VRAM)

```bat
cd ml\acne_model
python -m venv venv
venv\Scripts\activate.bat

:: CPU-only PyTorch (safe default). The MX350 has only 2 GB VRAM; it
:: can train resnet18 at 224px with batch_size 8-16, but CPU is the
:: reliable fallback. Do NOT assume CUDA works just because the NVIDIA
:: driver reports a CUDA version.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install scikit-learn matplotlib PyYAML Pillow

:: Put ACNE04 in ml\acne_model\data\ACNE04 , then:
python inspect_dataset.py --config configs\default.yaml
python train.py --config configs\default.yaml
python evaluate.py --config configs\default.yaml
```

To actually use your GPU on Windows, install a CUDA build of PyTorch
matching your driver (see pytorch.org), then confirm:
```python
python -c "import torch; print(torch.cuda.is_available())"
```
If that prints `False`, training falls back to CPU automatically — the
code never assumes CUDA.

## Outputs (written to `outputs/`)

| File | What it is |
|------|------------|
| `best_model.pth` | model weights (best validation macro-F1) |
| `class_mapping.json` | index → class name (the ground-truth label map) |
| `preprocessing.json` | image size + normalization + arch (backend needs this) |
| `training_config.json` | full resolved config (reproducibility) |
| `train_log.json` | per-epoch metrics actually observed |
| `test_split.json` | the exact held-out test images (so evaluation is reproducible and leak-free) |
| `evaluation_report.json` | accuracy, per-class P/R/F1, confusion matrix, ROC-AUC/PR-AUC |
| `confusion_matrix.png` | confusion matrix plot |

## Configuration (`configs/default.yaml`)

Key things you may need to change after inspection:
- `dataset.label_mode`: `"annotation"` (filename→label file) or
  `"imagefolder"` (per-class subfolders).
- `dataset.annotation_file` / `dataset.images_subdir`: set explicitly if
  auto-detect picks the wrong file.
- `dataset.class_names`: must match the number of distinct labels found.
- `dataset.group_id_regex`: if filenames encode a patient/source id, set
  this so splitting is done by group (prevents the same patient landing
  in both train and test). If left empty, splitting is image-level
  stratified and the inspector warns that leakage can't be fully ruled
  out.
- `model.arch`: `resnet18` or `efficientnet_b0`.
- `training.batch_size`: lower to 8 if you hit GPU out-of-memory.

## Leakage, imbalance, and honesty guarantees

- **Train/val/test are kept separate.** The test split is saved to
  `test_split.json` and only `evaluate.py` touches it.
- **Group-aware splitting** when a patient/source id is available;
  otherwise stratified image-level with an explicit warning.
- **Class imbalance** handled via inverse-frequency class weights
  computed from the **train split only**.
- **No fabrication.** If the dataset is missing, the tools stop. Metrics
  are only ever written from real model outputs on the real test images.
  There is no dummy-checkpoint path.

## Troubleshooting

- **"Dataset root not found"** — set `dataset.root` to where you
  extracted ACNE04.
- **"No annotation file found"** — set `dataset.annotation_file`
  explicitly (check the inspection output for what's in the folder).
- **"Discovered N distinct labels but config lists M"** — update
  `dataset.class_names` to match the real labels, then re-run.
- **CUDA out of memory** — lower `training.batch_size` to 8, or
  `preprocessing.image_size` to 192.
- **`torch.cuda.is_available()` is False on a GPU machine** — you
  installed the CPU build; install a CUDA build matching your driver.
- **ROC-AUC is `nan` / coverage warning** — your test split is missing a
  class (usually: dataset or split too small). Not a code bug; a data
  signal.

## After training: handing the checkpoint back for integration

Once you've run this on the real data, share:
`best_model.pth`, `class_mapping.json`, `preprocessing.json`, and
`evaluation_report.json`. The backend's `app/services/acne_service.py`
will then be wired to load that verified checkpoint — and only then will
`/api/v1/acne/analyze` return real (still clearly non-diagnostic,
experimental) predictions instead of `model_not_configured`.
