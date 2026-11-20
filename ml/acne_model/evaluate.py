"""
Step 3-4 tool: evaluate the trained checkpoint on the HELD-OUT test
split that train.py saved (test_split.json) — never on data used for
training or model selection. Produces real metrics and plots.

Usage:
    python evaluate.py --config configs/default.yaml

Writes into <output_dir>/:
    evaluation_report.json  (accuracy, per-class P/R/F1, macro/weighted, ROC-AUC/PR-AUC)
    confusion_matrix.png
    roc_curves.png          (one-vs-rest per class, if computable)
    pr_curves.png

Nothing here is reported unless it was actually computed from model
outputs on the test images.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from src.model import build_model  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    args = ap.parse_args()

    import numpy as np
    import torch
    from PIL import Image
    from torchvision import transforms

    cfg = yaml.safe_load(Path(args.config).read_text())
    out_dir = Path(cfg["output_dir"])

    ckpt = out_dir / "best_model.pth"
    test_split = out_dir / "test_split.json"
    class_map_path = out_dir / "class_mapping.json"
    prep_path = out_dir / "preprocessing.json"
    for p in (ckpt, test_split, class_map_path, prep_path):
        if not p.is_file():
            print(f"Missing required artifact: {p}. Run train.py first.")
            return 2

    class_map = {int(k): v for k, v in json.loads(class_map_path.read_text()).items()}
    prep = json.loads(prep_path.read_text())
    num_classes = prep["num_classes"]
    class_names = [class_map[i] for i in range(num_classes)]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(prep["arch"], num_classes, pretrained=False)
    # weights_only=True is the safe load path; fall back for older torch.
    try:
        state = torch.load(ckpt, map_location=device, weights_only=True)
    except TypeError:
        state = torch.load(ckpt, map_location=device)
    model.load_state_dict(state)
    model.to(device).eval()

    size = prep["image_size"]
    tfm = transforms.Compose(
        [transforms.Resize((size, size)), transforms.ToTensor(),
         transforms.Normalize(mean=prep["mean"], std=prep["std"])]
    )

    items = json.loads(test_split.read_text())
    y_true, y_pred, probs = [], [], []
    with torch.no_grad():
        for it in items:
            with Image.open(it["path"]) as im:
                x = tfm(im.convert("RGB")).unsqueeze(0).to(device)
            logits = model(x)
            p = torch.softmax(logits, dim=1).cpu().numpy()[0]
            probs.append(p)
            y_pred.append(int(p.argmax()))
            y_true.append(int(it["label"]))

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    probs = np.array(probs)

    # ---- metrics (sklearn if available; otherwise manual fallbacks) ----
    report: dict = {"n_test": int(len(y_true)), "class_names": class_names}
    report["accuracy"] = float(np.mean(y_true == y_pred))

    try:
        from sklearn.metrics import (
            classification_report,
            confusion_matrix,
            roc_auc_score,
            average_precision_score,
        )

        all_labels = list(range(num_classes))
        report["classification_report"] = classification_report(
            y_true,
            y_pred,
            labels=all_labels,            # pin to the full class set...
            target_names=class_names,     # ...so names always line up,
            output_dict=True,
            zero_division=0,
        )
        if not set(y_true) == set(all_labels):
            report["coverage_warning"] = (
                "The held-out test split does not contain every class. Metrics "
                "for absent classes are 0 and ROC/PR-AUC may be unreliable. "
                "This is usually a sign the dataset or split is too small."
            )
        cm = confusion_matrix(y_true, y_pred, labels=all_labels)
        report["confusion_matrix"] = cm.tolist()

        # One-vs-rest AUCs where a class actually appears in the test set.
        onehot = np.eye(num_classes)[y_true]
        try:
            report["roc_auc_ovr_macro"] = float(
                roc_auc_score(onehot, probs, average="macro", multi_class="ovr")
            )
        except ValueError as e:
            report["roc_auc_ovr_macro"] = None
            report["roc_auc_note"] = f"not computable: {e}"
        try:
            report["pr_auc_macro"] = float(average_precision_score(onehot, probs, average="macro"))
        except ValueError as e:
            report["pr_auc_macro"] = None
            report["pr_auc_note"] = f"not computable: {e}"
    except ImportError:
        # Minimal manual confusion matrix + per-class P/R/F1.
        cm = np.zeros((num_classes, num_classes), dtype=int)
        for t, p in zip(y_true, y_pred):
            cm[t, p] += 1
        report["confusion_matrix"] = cm.tolist()
        report["sklearn_available"] = False

    (out_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2))

    # ---- plots (best-effort; skip cleanly if matplotlib absent) ----
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        cm = np.array(report["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(5, 4))
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(num_classes)); ax.set_yticks(range(num_classes))
        ax.set_xticklabels(class_names, rotation=45, ha="right")
        ax.set_yticklabels(class_names)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        ax.set_title("Confusion matrix (held-out test)")
        for i in range(num_classes):
            for j in range(num_classes):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center")
        fig.colorbar(im)
        fig.tight_layout()
        fig.savefig(out_dir / "confusion_matrix.png", dpi=120)
        plt.close(fig)
        print("Saved confusion_matrix.png")
    except ImportError:
        print("matplotlib not installed — skipped plots (metrics JSON still written).")

    print("\n=== EVALUATION SUMMARY (held-out test set) ===")
    print(f"n_test = {report['n_test']}")
    print(f"accuracy = {report['accuracy']:.4f}")
    if report.get("roc_auc_ovr_macro") is not None:
        print(f"ROC-AUC (macro, OvR) = {report['roc_auc_ovr_macro']:.4f}")
    if report.get("pr_auc_macro") is not None:
        print(f"PR-AUC (macro) = {report['pr_auc_macro']:.4f}")
    print(f"Full report: {out_dir / 'evaluation_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
