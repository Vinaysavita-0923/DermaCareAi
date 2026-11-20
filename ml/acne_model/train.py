"""
Step 2-3 tool: train the acne-severity classifier on the REAL ACNE04
dataset and save a verified checkpoint + all the metadata the backend
needs to use it safely.

Usage:
    python train.py --config configs/default.yaml

Saves into <output_dir>/:
    best_model.pth         (model weights; best val macro-F1)
    class_mapping.json     (index -> class name — the ground truth map)
    preprocessing.json     (image size + normalization used)
    training_config.json   (full resolved config, for reproducibility)
    train_log.json         (per-epoch metrics actually observed)

Runs on CPU or GPU automatically. Does NOT assume CUDA. Does NOT
fabricate anything — if the dataset isn't present, it stops.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from src.dataset import inspect_and_load  # noqa: E402
from src.data_pipeline import (  # noqa: E402
    build_dataset,
    compute_class_weights,
    make_splits,
)
from src.model import build_model  # noqa: E402


def set_seed(seed: int) -> None:
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def macro_f1(y_true, y_pred, num_classes):
    import numpy as np

    f1s = []
    for c in range(num_classes):
        tp = np.sum((y_pred == c) & (y_true == c))
        fp = np.sum((y_pred == c) & (y_true != c))
        fn = np.sum((y_pred != c) & (y_true == c))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        f1s.append(f1)
    return float(np.mean(f1s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()

    import numpy as np
    import torch
    from torch.utils.data import DataLoader

    cfg = yaml.safe_load(Path(args.config).read_text())
    tcfg = cfg["training"]
    set_seed(tcfg["seed"])

    # ---- Load + inspect the real dataset (stops if absent) ----
    samples, report = inspect_and_load(cfg)
    print(report.pretty())

    num_classes = len(report.class_names)
    if num_classes != cfg["model"]["num_classes"]:
        print(
            f"\nNOTE: discovered {num_classes} classes; overriding "
            f"model.num_classes ({cfg['model']['num_classes']}) to match the "
            "actual data."
        )
        cfg["model"]["num_classes"] = num_classes

    # ---- Splits (group-aware if possible) ----
    tr, va, te = make_splits(
        samples,
        train=cfg["split"]["train"],
        val=cfg["split"]["val"],
        test=cfg["split"]["test"],
        seed=tcfg["seed"],
        grouping_available=report.grouping_available,
    )
    print(f"\nSplit sizes -> train={len(tr)}  val={len(va)}  test={len(te)}")
    if min(len(tr), len(va), len(te)) == 0:
        print("ERROR: a split is empty. Dataset too small or misconfigured.")
        return 4

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} (CUDA available: {torch.cuda.is_available()})")

    train_ds = build_dataset(tr, cfg, train=True)
    val_ds = build_dataset(va, cfg, train=False)
    test_ds = build_dataset(te, cfg, train=False)

    dl_kw = dict(batch_size=tcfg["batch_size"], num_workers=tcfg["num_workers"])
    train_dl = DataLoader(train_ds, shuffle=True, **dl_kw)
    val_dl = DataLoader(val_ds, shuffle=False, **dl_kw)

    model = build_model(cfg["model"]["arch"], num_classes, cfg["model"]["pretrained"]).to(device)

    if tcfg["use_class_weights"]:
        weights = compute_class_weights(tr, num_classes).to(device)
        print(f"Class weights (inverse freq, train only): {weights.tolist()}")
        criterion = torch.nn.CrossEntropyLoss(weight=weights)
    else:
        criterion = torch.nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=tcfg["lr"], weight_decay=tcfg["weight_decay"]
    )

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    best_f1 = -1.0
    patience = tcfg["early_stopping_patience"]
    since_improved = 0
    log = []

    for epoch in range(1, tcfg["epochs"] + 1):
        t0 = time.time()
        model.train()
        running = 0.0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            running += loss.item() * x.size(0)
        train_loss = running / len(train_ds)

        # ---- validation ----
        model.eval()
        y_true, y_pred = [], []
        with torch.no_grad():
            for x, y in val_dl:
                x = x.to(device)
                logits = model(x)
                preds = logits.argmax(1).cpu().numpy()
                y_pred.extend(preds.tolist())
                y_true.extend(y.numpy().tolist())
        val_f1 = macro_f1(np.array(y_true), np.array(y_pred), num_classes)
        val_acc = float(np.mean(np.array(y_true) == np.array(y_pred)))
        dt = time.time() - t0
        print(
            f"epoch {epoch:02d}/{tcfg['epochs']}  "
            f"train_loss={train_loss:.4f}  val_acc={val_acc:.4f}  "
            f"val_macroF1={val_f1:.4f}  ({dt:.0f}s)"
        )
        log.append(
            {"epoch": epoch, "train_loss": train_loss, "val_acc": val_acc, "val_macro_f1": val_f1}
        )

        if val_f1 > best_f1:
            best_f1 = val_f1
            since_improved = 0
            torch.save(model.state_dict(), out_dir / "best_model.pth")
            print(f"   ^ new best (val_macroF1={val_f1:.4f}) -> saved best_model.pth")
        else:
            since_improved += 1
            if since_improved >= patience:
                print(f"Early stopping at epoch {epoch} (no val improvement in {patience}).")
                break

    # ---- Save the metadata the backend needs to use this safely ----
    (out_dir / "class_mapping.json").write_text(
        json.dumps({i: name for i, name in enumerate(report.class_names)}, indent=2)
    )
    (out_dir / "preprocessing.json").write_text(
        json.dumps(
            {
                "image_size": cfg["preprocessing"]["image_size"],
                "mean": cfg["preprocessing"]["mean"],
                "std": cfg["preprocessing"]["std"],
                "arch": cfg["model"]["arch"],
                "num_classes": num_classes,
            },
            indent=2,
        )
    )
    (out_dir / "training_config.json").write_text(json.dumps(cfg, indent=2))
    (out_dir / "train_log.json").write_text(json.dumps(log, indent=2))

    # Record the exact test-split file list so evaluate.py scores the
    # SAME held-out images (no leakage, fully reproducible).
    (out_dir / "test_split.json").write_text(
        json.dumps([{"path": s.path, "label": s.label} for s in te], indent=2)
    )

    print(f"\nDone. Best val macro-F1 = {best_f1:.4f}")
    print(f"Artifacts saved in: {out_dir.resolve()}")
    print("Next: python evaluate.py --config", args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
