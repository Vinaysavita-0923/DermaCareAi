"""
Build a learned skin-vs-not-skin gate (BUILD TIME ONLY — torch/torchvision/
sklearn/pyarrow are not shipped; runtime needs onnxruntime + numpy).

  1. Stream every training image ONCE through three pretrained ImageNet
     backbones (MobileNetV3-Small, MobileNetV3-Large, EfficientNet-B0) and
     cache the pooled features — images are never all held in memory.
  2. For each backbone, train a logistic-regression head; report held-out
     accuracy per source.
  3. Fold the head into the network (Linear + Sigmoid) and export ONE
     self-contained ONNX per backbone that outputs P(skin).
  4. Validate each EXPORTED onnx on real images it never saw in training
     (see VALID_SKIN / VALID_NOTSKIN), then install MobileNetV3-Large as
     backend/app/ml_models/skin_gate.onnx.

Skin (1):     LFW portraits + face crops, SCIN phone photos, DermNet close-ups
Not skin (0): Imagenette photos, CIFAR-10 objects, cartoons, solids/noise

Run fetch_data.py first (downloads everything into ./data), then:
    python train_gate.py
"""
from __future__ import annotations

import io
import os
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
INPUT = 224
BATCH = 64
RNG = np.random.default_rng(42)
BACKBONES = ("mobilenet_v3_small", "mobilenet_v3_large", "efficientnet_b0")

REPO = Path(__file__).resolve().parents[2]
ONNX_OUT = REPO / "backend" / "app" / "ml_models"


def _images_in(folder: str | None) -> list[Path]:
    if not folder:
        return []
    return sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


# Never trained on — explicit real-world validation only. The team portraits
# ship with the repo; point SKIN_GATE_VALID_SKIN / SKIN_GATE_VALID_NOTSKIN at
# folders of your own real-world test photos to extend the check.
VALID_SKIN = sorted((REPO / "frontend" / "public" / "team").glob("*.jpg")) + _images_in(
    os.environ.get("SKIN_GATE_VALID_SKIN"))
VALID_NOTSKIN = _images_in(os.environ.get("SKIN_GATE_VALID_NOTSKIN"))


def pil_to_chw(img: Image.Image) -> np.ndarray:
    img = img.convert("RGB").resize((INPUT, INPUT))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return ((arr - IMAGENET_MEAN) / IMAGENET_STD).transpose(2, 0, 1)


def random_crop(img: Image.Image, lo=0.45, hi=0.75) -> Image.Image:
    """A random sub-region — simulates the tighter close-ups users upload."""
    w, h = img.size
    s = RNG.uniform(lo, hi)
    cw, ch = max(8, int(w * s)), max(8, int(h * s))
    x0 = int(RNG.integers(0, max(1, w - cw + 1)))
    y0 = int(RNG.integers(0, max(1, h - ch + 1)))
    return img.crop((x0, y0, x0 + cw, y0 + ch))


# ---------- sources: each yields PIL images lazily ----------

def from_files(paths, crops=False):
    for p in paths:
        try:
            img = Image.open(p).convert("RGB")
        except Exception:
            continue
        yield img
        if crops:
            yield random_crop(img)


def from_parquet(path: Path, col: str, n: int):
    import pyarrow.parquet as pq
    rows = pq.read_table(path, columns=[col]).column(col)
    for i in RNG.permutation(len(rows))[:n]:
        yield Image.open(io.BytesIO(rows[int(i)].as_py()["bytes"])).convert("RGB")


def synthetic():
    for _ in range(60):
        yield Image.new("RGB", (INPUT, INPUT), tuple(int(x) for x in RNG.integers(60, 230, 3)))
    for _ in range(60):
        yield Image.fromarray(RNG.integers(0, 256, (INPUT, INPUT, 3), dtype=np.uint8))


def sources():
    lfw = sorted((DATA / "lfw_home" / "lfw_funneled").glob("*/*.jpg"))
    order = [lfw[i] for i in RNG.permutation(len(lfw))]
    # LFW frames are 250x250 head-and-shoulders portraits; the centre crop is a close-up face.
    face_crops = (Image.open(p).convert("RGB").crop((70, 60, 180, 190)) for p in order[700:1000])
    return {
        # --- skin (1) ---
        "lfw_portraits": (from_files(order[:700]), 1),
        "lfw_face_crops": (face_crops, 1),
        "scin_phone_skin": (from_files(sorted((DATA / "skin" / "scin").iterdir()), crops=True), 1),
        "dermnet_clinical": (from_files(sorted((DATA / "skin" / "dermnet").iterdir()), crops=True), 1),
        # --- not skin (0) ---
        "imagenette_photos": (from_parquet(DATA / "notskin" / "imagenette.parquet", "image", 1963), 0),
        "cifar_objects": (from_parquet(DATA / "hf_test" / "cifar10_test.parquet", "img", 700), 0),
        "cartoons": (from_files(sorted((DATA / "notskin" / "cartoon").iterdir())), 0),
        "synthetic": (synthetic(), 0),
    }


# ---------- backbones ----------

def build_backbone(name: str):
    import torch
    import torchvision
    tm = torchvision.models
    net = {
        "mobilenet_v3_small": lambda: tm.mobilenet_v3_small(weights=tm.MobileNet_V3_Small_Weights.IMAGENET1K_V1),
        "mobilenet_v3_large": lambda: tm.mobilenet_v3_large(weights=tm.MobileNet_V3_Large_Weights.IMAGENET1K_V2),
        "efficientnet_b0": lambda: tm.efficientnet_b0(weights=tm.EfficientNet_B0_Weights.IMAGENET1K_V1),
    }[name]()

    class Feat(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.features = m.features
            self.avgpool = m.avgpool

        def forward(self, x):
            return torch.flatten(self.avgpool(self.features(x)), 1)

    return Feat(net).eval()


def extract_all(backbones: dict, images) -> dict[str, np.ndarray]:
    """One pass over `images`, batched; returns features per backbone."""
    import torch
    feats = {k: [] for k in backbones}
    batch = []

    def flush():
        if not batch:
            return
        t = torch.from_numpy(np.stack(batch))
        with torch.no_grad():
            for k, bb in backbones.items():
                feats[k].append(bb(t).numpy())
        batch.clear()

    for img in images:
        batch.append(pil_to_chw(img))
        if len(batch) == BATCH:
            flush()
    flush()
    return {k: np.concatenate(v) if v else np.zeros((0, 1), np.float32) for k, v in feats.items()}


def main():
    import onnxruntime as ort
    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    print("Building backbones ...", flush=True)
    backbones = {k: build_backbone(k) for k in BACKBONES}

    cache = HERE / "features.npz"
    if cache.exists():
        print("Using cached features", flush=True)
        z = np.load(cache, allow_pickle=False)
        X = {k: z[k] for k in BACKBONES}
        y, tag = z["y"], z["tag"]
    else:
        print("Extracting features (one streamed pass) ...", flush=True)
        X = {k: [] for k in BACKBONES}
        y, tag = [], []
        for name, (imgs, lab) in sources().items():
            f = extract_all(backbones, imgs)
            n = len(next(iter(f.values())))
            print(f"  {name:20s} {n:5d}  label={lab}", flush=True)
            for k in BACKBONES:
                X[k].append(f[k])
            y.append(np.full(n, lab))
            tag.append(np.full(n, name))
        X = {k: np.concatenate(v) for k, v in X.items()}
        y, tag = np.concatenate(y), np.concatenate(tag)
        np.savez(cache, y=y, tag=tag, **X)

    def stack(paths):
        return np.stack([pil_to_chw(Image.open(p)) for p in paths]) if paths else None

    local_pos, local_neg = stack(VALID_SKIN), stack(VALID_NOTSKIN)
    idx_tr, idx_te = train_test_split(np.arange(len(y)), test_size=0.2, random_state=42, stratify=tag)

    for name in BACKBONES:
        Xk = X[name]
        clf = LogisticRegression(max_iter=5000, C=0.5, class_weight="balanced")
        clf.fit(Xk[idx_tr], y[idx_tr])
        acc = clf.score(Xk[idx_te], y[idx_te])
        per_source = []
        for src in dict.fromkeys(tag):
            m = idx_te[tag[idx_te] == src]
            per_source.append(f"  {src:20s} n={len(m):4d}  correct={clf.score(Xk[m], y[m]):.3f}")

        w = torch.tensor(clf.coef_.astype(np.float32))
        b = torch.tensor(clf.intercept_.astype(np.float32))

        class Gate(torch.nn.Module):
            def __init__(self, bb):
                super().__init__()
                self.bb = bb
                self.lin = torch.nn.Linear(w.shape[1], 1)
                with torch.no_grad():
                    self.lin.weight.copy_(w)
                    self.lin.bias.copy_(b)

            def forward(self, x):
                return torch.sigmoid(self.lin(self.bb(x)))  # (B, 1) P(skin)

        onnx_path = HERE / f"skin_gate_{name}.onnx"
        torch.onnx.export(
            Gate(backbones[name]).eval(), torch.zeros(1, 3, INPUT, INPUT), str(onnx_path),
            input_names=["input"], output_names=["skin_prob"],
            dynamic_axes={"input": {0: "batch"}, "skin_prob": {0: "batch"}},
            opset_version=13, dynamo=False,
        )
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

        def probs(arr):
            return sess.run(None, {"input": arr})[0].ravel() if arr is not None else np.array([])

        pos, neg = probs(local_pos), probs(local_neg)
        lines = [f"=== {name}  ({onnx_path.stat().st_size / 1e6:.1f} MB)  held-out acc {acc:.4f}",
                 *per_source,
                 "  real skin (want high):  " + "  ".join(f"{p.stem}={v:.3f}" for p, v in zip(VALID_SKIN, pos)),
                 "  not skin  (want low):   " + "  ".join(f"{p.stem}={v:.3f}" for p, v in zip(VALID_NOTSKIN, neg))]
        if len(pos) and len(neg):
            lines.append(f"  margin (min skin - max not-skin): {pos.min() - neg.max():+.3f}")
        report = "\n".join(lines)
        (HERE / f"report_{name}.txt").write_text(report, encoding="utf-8")
        print(report, flush=True)

    # The shipped gate is MobileNetV3-Large: the widest real-world margin at
    # 12 MB (see README). Copy it to where the backend loads it from.
    shutil.copyfile(HERE / "skin_gate_mobilenet_v3_large.onnx", ONNX_OUT / "skin_gate.onnx")
    print(f"Installed {ONNX_OUT / 'skin_gate.onnx'}", flush=True)


if __name__ == "__main__":
    main()
