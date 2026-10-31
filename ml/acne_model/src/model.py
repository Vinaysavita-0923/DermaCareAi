"""
Model factory: lightweight transfer-learning backbones sized for a
2 GB-VRAM GPU or CPU. torch/torchvision imported lazily.
"""
from __future__ import annotations


def build_model(arch: str, num_classes: int, pretrained: bool):
    import torch.nn as nn
    from torchvision import models

    arch = arch.lower()
    if arch == "resnet18":
        weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        model = models.resnet18(weights=weights)
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
        return model
    if arch == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        model = models.efficientnet_b0(weights=weights)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model
    raise ValueError(f"Unknown arch '{arch}'. Use 'resnet18' or 'efficientnet_b0'.")
