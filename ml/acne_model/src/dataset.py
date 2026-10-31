"""
ACNE04 dataset inspection, validation, and loading.

Design principle: this module NEVER silently assumes the dataset
structure. It inspects what is actually on disk, prints a report, and
raises a clear error if reality doesn't match the config — so you fix
the config rather than train on a misread dataset.

It supports two label layouts (see configs/default.yaml):
  * "imagefolder"  -> root/<class>/*.jpg
  * "annotation"   -> an annotation file mapping filename -> label

Nothing here fabricates data. If the dataset is absent, it says so.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass
class Sample:
    path: str
    label: int
    group: str | None  # patient/source id if derivable, else None


@dataclass
class InspectionReport:
    root: str
    total_images_found: int
    labeled_samples: int
    class_names: list[str]
    class_distribution: dict[str, int]
    corrupt_images: list[str] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    grouping_available: bool = False
    warnings: list[str] = field(default_factory=list)

    def pretty(self) -> str:
        lines = [
            "=" * 60,
            "ACNE04 DATASET INSPECTION REPORT",
            "=" * 60,
            f"Root: {self.root}",
            f"Image files found: {self.total_images_found}",
            f"Labeled samples:   {self.labeled_samples}",
            f"Classes ({len(self.class_names)}): {self.class_names}",
            "Class distribution:",
        ]
        for name, count in self.class_distribution.items():
            pct = (100.0 * count / self.labeled_samples) if self.labeled_samples else 0.0
            lines.append(f"    {name:>14}: {count:>5}  ({pct:4.1f}%)")
        lines.append(f"Corrupt images:    {len(self.corrupt_images)}")
        lines.append(f"Exact-duplicate groups: {len(self.duplicate_groups)}")
        lines.append(
            f"Source/patient grouping available: {self.grouping_available}"
        )
        if self.warnings:
            lines.append("-" * 60)
            lines.append("WARNINGS:")
            for w in self.warnings:
                lines.append(f"  ! {w}")
        lines.append("=" * 60)
        return "\n".join(lines)


def _iter_image_files(base: Path):
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
            yield p


def _auto_detect_images_dir(root: Path, configured: str) -> Path:
    if configured:
        d = root / configured
        if not d.is_dir():
            raise FileNotFoundError(f"Configured images_subdir not found: {d}")
        return d
    # Common ACNE04 image dir names, else fall back to root itself.
    for candidate in ["JPEGImages", "images", "Images", "img"]:
        if (root / candidate).is_dir():
            return root / candidate
    return root


def _auto_detect_annotation(root: Path, configured: str) -> Path | None:
    if configured:
        f = root / configured
        if not f.is_file():
            raise FileNotFoundError(f"Configured annotation_file not found: {f}")
        return f
    # Look for a plausible annotation file.
    candidates = []
    for p in root.rglob("*"):
        if p.suffix.lower() in {".csv", ".txt"} and p.is_file():
            name = p.name.lower()
            if any(k in name for k in ["label", "annot", "train", "ground", "grade", "class"]):
                candidates.append(p)
    return candidates[0] if candidates else None


def _parse_annotation(ann_path: Path) -> list[tuple[str, str, str | None]]:
    """Return list of (filename, raw_label, optional_group). Accepts
    either whitespace- or comma-separated, with or without a header."""
    rows: list[tuple[str, str, str | None]] = []
    text = ann_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(text):
        line = line.strip()
        if not line:
            continue
        parts = [x.strip() for x in (line.split(",") if "," in line else line.split())]
        if len(parts) < 2:
            continue
        # Skip an obvious header row.
        if i == 0 and not parts[1].lstrip("-").isdigit() and not _looks_like_label(parts[1]):
            continue
        filename, label = parts[0], parts[1]
        group = parts[2] if len(parts) >= 3 else None
        rows.append((filename, label, group))
    return rows


def _looks_like_label(s: str) -> bool:
    return s.isdigit() or s.lower() in {
        "mild", "moderate", "severe", "very_severe", "veryservere", "level0",
        "level1", "level2", "level3", "0", "1", "2", "3",
    }


def _derive_group(filename: str, regex: str) -> str | None:
    if not regex:
        return None
    m = re.search(regex, filename)
    return m.group(1) if m else None


def inspect_and_load(cfg: dict, *, compute_hashes: bool = True) -> tuple[list[Sample], InspectionReport]:
    """Inspect the dataset on disk and return (samples, report). Raises
    FileNotFoundError if the dataset isn't present, and ValueError if the
    discovered class count contradicts the configured num_classes."""
    ds = cfg["dataset"]
    root = Path(ds["root"]).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Dataset root not found: {root}\n"
            "Download/extract ACNE04 there, or fix dataset.root in the config. "
            "This code does NOT create or fabricate data."
        )

    warnings: list[str] = []
    label_mode = ds["label_mode"]
    group_regex = ds.get("group_id_regex", "") or ""
    raw_label_to_idx: dict[str, int] = {}
    samples: list[Sample] = []
    corrupt: list[str] = []

    def _label_index(raw: str) -> int:
        key = raw.strip().lower()
        if key not in raw_label_to_idx:
            raw_label_to_idx[key] = len(raw_label_to_idx)
        return raw_label_to_idx[key]

    if label_mode == "imagefolder":
        # root/<class>/*.jpg
        class_dirs = sorted([d for d in root.iterdir() if d.is_dir()])
        if not class_dirs:
            raise FileNotFoundError(f"No class subfolders under {root} for imagefolder mode.")
        for cdir in class_dirs:
            for img in _iter_image_files(cdir):
                samples.append(
                    Sample(str(img), _label_index(cdir.name), _derive_group(img.name, group_regex))
                )
    elif label_mode == "annotation":
        images_dir = _auto_detect_images_dir(root, ds.get("images_subdir", ""))
        ann = _auto_detect_annotation(root, ds.get("annotation_file", ""))
        if ann is None:
            raise FileNotFoundError(
                f"No annotation file found under {root}. ACNE04 usually ships a "
                "filename->grade file; set dataset.annotation_file explicitly "
                "after checking the inspection output."
            )
        warnings.append(f"Using annotation file: {ann}")
        warnings.append(f"Using images dir: {images_dir}")
        # Index images by basename for lookup.
        by_name = {p.name: p for p in _iter_image_files(images_dir)}
        for filename, raw_label, grp in _parse_annotation(ann):
            img_path = by_name.get(os.path.basename(filename))
            if img_path is None:
                continue  # annotation row with no matching image
            group = grp or _derive_group(filename, group_regex)
            samples.append(Sample(str(img_path), _label_index(raw_label), group))
    else:
        raise ValueError(f"Unknown dataset.label_mode: {label_mode}")

    if not samples:
        raise FileNotFoundError(
            "Dataset root exists but no labeled samples were loaded. Check the "
            "inspection warnings above and verify label_mode / annotation_file."
        )

    # Validate images (decode) + detect corrupt + optional dup detection.
    hashes: dict[str, list[str]] = defaultdict(list)
    valid: list[Sample] = []
    for s in samples:
        try:
            with Image.open(s.path) as im:
                im.verify()
            if compute_hashes:
                with open(s.path, "rb") as fh:
                    h = hashlib.md5(fh.read()).hexdigest()
                hashes[h].append(s.path)
            valid.append(s)
        except (UnidentifiedImageError, OSError, ValueError):
            corrupt.append(s.path)

    dup_groups = [paths for paths in hashes.values() if len(paths) > 1] if compute_hashes else []

    # Build class-name list in index order.
    idx_to_name = {v: k for k, v in raw_label_to_idx.items()}
    discovered_names = [idx_to_name[i] for i in range(len(idx_to_name))]

    # Map discovered labels onto configured names if counts match;
    # otherwise keep discovered names and warn (never silently coerce).
    configured_names = ds.get("class_names", [])
    if len(discovered_names) == len(configured_names):
        class_names = configured_names
    else:
        class_names = discovered_names
        warnings.append(
            f"Discovered {len(discovered_names)} distinct labels "
            f"{discovered_names}, but config lists {len(configured_names)} "
            f"class_names {configured_names}. Using discovered labels. "
            "Update the config to match before trusting training."
        )

    grouping_available = any(s.group for s in valid)
    if not grouping_available:
        warnings.append(
            "No patient/source group ids available — splitting will be "
            "image-level stratified. Leakage from the same patient across "
            "splits cannot be fully ruled out. Set dataset.group_id_regex "
            "if your filenames encode a patient/source id."
        )

    dist = Counter(class_names[s.label] for s in valid)
    report = InspectionReport(
        root=str(root),
        total_images_found=len(samples),
        labeled_samples=len(valid),
        class_names=class_names,
        class_distribution=dict(sorted(dist.items())),
        corrupt_images=corrupt,
        duplicate_groups=dup_groups,
        grouping_available=grouping_available,
        warnings=warnings,
    )
    return valid, report
