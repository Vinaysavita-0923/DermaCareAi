"""
Turns the inspected Sample list into reproducible train/val/test splits
and PyTorch Datasets. torch/torchvision are imported lazily so that
dataset INSPECTION (src/dataset.py) works without them installed.
"""
from __future__ import annotations

import random
from collections import defaultdict

from src.dataset import Sample


def make_splits(
    samples: list[Sample],
    *,
    train: float,
    val: float,
    test: float,
    seed: int,
    grouping_available: bool,
) -> tuple[list[Sample], list[Sample], list[Sample]]:
    """Split into train/val/test.

    If group ids are available, split BY GROUP so no patient/source
    appears in more than one split (prevents leakage). Otherwise fall
    back to a stratified image-level split. Deterministic given `seed`.
    """
    assert abs((train + val + test) - 1.0) < 1e-6, "split fractions must sum to 1.0"
    rng = random.Random(seed)

    if grouping_available:
        groups: dict[str, list[Sample]] = defaultdict(list)
        for s in samples:
            groups[s.group or f"__ungrouped_{id(s)}"].append(s)
        group_ids = sorted(groups.keys())
        rng.shuffle(group_ids)
        n = len(group_ids)
        n_train = int(n * train)
        n_val = int(n * val)
        train_g = set(group_ids[:n_train])
        val_g = set(group_ids[n_train : n_train + n_val])
        tr, va, te = [], [], []
        for g in group_ids:
            bucket = tr if g in train_g else va if g in val_g else te
            bucket.extend(groups[g])
        return tr, va, te

    # Stratified image-level split (per class), so class balance is kept.
    by_class: dict[int, list[Sample]] = defaultdict(list)
    for s in samples:
        by_class[s.label].append(s)
    tr, va, te = [], [], []
    for _, items in sorted(by_class.items()):
        items = items[:]
        rng.shuffle(items)
        n = len(items)
        n_train = int(n * train)
        n_val = int(n * val)
        tr += items[:n_train]
        va += items[n_train : n_train + n_val]
        te += items[n_train + n_val :]
    rng.shuffle(tr); rng.shuffle(va); rng.shuffle(te)
    return tr, va, te


def build_transforms(cfg: dict, *, train: bool):
    """Returns torchvision transforms. Imported lazily."""
    from torchvision import transforms

    pp = cfg["preprocessing"]
    size = pp["image_size"]
    norm = transforms.Normalize(mean=pp["mean"], std=pp["std"])

    if train:
        return transforms.Compose(
            [
                transforms.Resize((size + 16, size + 16)),
                transforms.RandomCrop(size),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(brightness=0.15, contrast=0.15),
                transforms.ToTensor(),
                norm,
            ]
        )
    return transforms.Compose(
        [transforms.Resize((size, size)), transforms.ToTensor(), norm]
    )


def build_dataset(samples: list[Sample], cfg: dict, *, train: bool):
    """Returns a torch Dataset. Imported lazily."""
    import torch
    from PIL import Image
    from torch.utils.data import Dataset

    tfm = build_transforms(cfg, train=train)

    class _AcneDataset(Dataset):
        def __init__(self, items):
            self.items = items

        def __len__(self):
            return len(self.items)

        def __getitem__(self, i):
            s = self.items[i]
            with Image.open(s.path) as im:
                im = im.convert("RGB")
                x = tfm(im)
            return x, torch.tensor(s.label, dtype=torch.long)

    return _AcneDataset(samples)


def compute_class_weights(train_samples: list[Sample], num_classes: int):
    """Inverse-frequency class weights from the TRAIN split only."""
    import torch

    counts = [0] * num_classes
    for s in train_samples:
        counts[s.label] += 1
    total = sum(counts)
    weights = [
        (total / (num_classes * c)) if c > 0 else 0.0 for c in counts
    ]
    return torch.tensor(weights, dtype=torch.float)
