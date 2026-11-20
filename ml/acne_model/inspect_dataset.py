"""
Step 1 tool: inspect the ACNE04 dataset and print a report WITHOUT
training anything. Run this first to verify structure, labels, class
distribution, corrupt images, and duplicates — then adjust the config
to match what it reports before training.

Usage:
    python inspect_dataset.py --config configs/default.yaml

Requires only PyYAML and Pillow (no torch).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from src.dataset import inspect_and_load  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument(
        "--no-hashes",
        action="store_true",
        help="skip duplicate detection (faster on very large datasets)",
    )
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    try:
        samples, report = inspect_and_load(cfg, compute_hashes=not args.no_hashes)
    except FileNotFoundError as e:
        print("DATASET NOT READY:\n", e)
        return 2
    except ValueError as e:
        print("DATASET CONFIG PROBLEM:\n", e)
        return 3

    print(report.pretty())
    print(f"\nLoaded {len(samples)} valid samples ready for training.")
    if report.corrupt_images:
        print(f"\nFirst few corrupt images:")
        for p in report.corrupt_images[:5]:
            print("   ", p)
    if report.duplicate_groups:
        print(f"\n{len(report.duplicate_groups)} exact-duplicate group(s) detected; "
              "consider de-duplicating to avoid train/test leakage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
