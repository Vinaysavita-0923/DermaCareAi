# Skin gate (skin vs. not skin)

The 22-class skin-condition classifier always picks *some* class — a meme or a
street photo used to come back as "Normal / Healthy Skin 84%". This gate runs
first and blocks anything that isn't a real photo of skin.

**Shipped model:** `backend/app/ml_models/skin_gate.onnx` (11.9 MB)
**Runtime:** `onnxruntime` + `numpy` only — none of this folder's
dependencies are deployed.

## How it works

1. A pretrained ImageNet **MobileNetV3-Large** (torchvision weights,
   frozen) turns a 224×224 image into a 960-number feature vector.
2. A **logistic-regression head** trained on those features outputs P(skin).
3. The head is folded into the network (Linear + Sigmoid) and exported as
   one self-contained ONNX file.
4. The backend rejects the upload when **P(skin) < 0.5**
   (`_MIN_SKIN_PROB` in `skin_condition_service.py`).

A colour-based rule was tried first and rejected: a meme scored *higher*
"skin fraction" (0.76) than a real face (0.13), so no threshold could work.

## Training data

| Source | Label | Images | Licence as published | Notes |
|---|---|---|---|---|
| LFW (Labeled Faces in the Wild) | skin | 700 portraits + 300 face crops | none stated; research dataset | real head-and-shoulders photos |
| SCIN, via `HawkFranklin-Research/SCIN-Dermatology-Raw-Images` | skin | 450 (+450 crops) | mirror: MIT | **original Google SCIN data has its own data-use terms** — check before commercial use |
| `raghad-murad/clinical-skin-disease` | skin | 280 (+280 crops) | mirror: Apache-2.0 | **images originate from DermNet**, which holds its own copyright |
| Imagenette 320px, `leandrodevai/imagenette-320px-resplit` | not skin | 1,963 | Apache-2.0 | real photos: objects, animals, vehicles, buildings |
| CIFAR-10 test split, `uoft-cs/cifar10` | not skin | 700 | none stated; research dataset | small object/animal images |
| `anokimchen/Cartoon_illustrations_i2i_1024x1024` | not skin | 500 | Apache-2.0 | cartoons incl. drawn people — drawn skin isn't real skin |
| Synthetic | not skin | 120 | — | flat colours (incl. skin tones) and noise |

The model weights don't contain the images, but if this goes into a
commercial product, have someone confirm the SCIN, DermNet, LFW and CIFAR
terms cover training use. The cleanly permissive sources alone (Imagenette,
cartoons, synthetic negatives) would not be enough skin examples to replace
them.

## Results

Held-out split (20%, stratified by source, never trained on):

| Backbone | Size | Held-out acc. | Weakest real skin photo | Pepe meme | Street photo | Margin |
|---|---|---|---|---|---|---|
| MobileNetV3-Small | 3.7 MB | 99.65% | 0.555 | 0.475 | 0.000 | +0.08 |
| **MobileNetV3-Large (shipped)** | **11.9 MB** | **99.74%** | **0.994** | **0.025** | **0.000** | **+0.97** |
| EfficientNet-B0 | 16.0 MB | 100% | 0.921 | 0.029 | 0.001 | +0.89 |

The "real-world" columns use photos the gate never saw: three team
portraits, four disease photos (acne, actinic keratosis on a cheek, bullous
disease on a torso, vitiligo on hands), a cartoon meme and a street photo.
Large was chosen for the widest gap between the two groups.

End to end through the API, the meme and street photo are rejected, and the
four disease photos are classified as Acne 95%, Actinic Keratosis 69%,
Bullous Disease 96% and Vitiligo 91%.

## Known limits

- It answers "is this a real photo of skin?", not "is this a clear,
  analysable close-up?". A real photo of a person far away may pass; the
  classifier's own low-confidence warning then applies.
- The real-world check is small (9 photos). Before relying on it, run
  `train_gate.py` with `SKIN_GATE_VALID_SKIN` / `SKIN_GATE_VALID_NOTSKIN`
  pointing at a larger folder of your own test photos, especially darker
  skin tones and body sites beyond the face.

## Re-training

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python fetch_data.py      # ~1 GB into ./data (git-ignored); fixed seeds
python train_gate.py      # benchmarks all three backbones, installs Large
```

Training takes ~10 minutes on a laptop CPU.
