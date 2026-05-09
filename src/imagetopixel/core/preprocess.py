from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter


@dataclass(frozen=True)
class PresetConfig:
    blur_strength: float
    sharpness_boost: float
    contrast_boost: float
    unsharp_percent: int


PRESETS: dict[str, PresetConfig] = {
    "standard": PresetConfig(blur_strength=0.20, sharpness_boost=1.05, contrast_boost=1.02, unsharp_percent=85),
    "sharper": PresetConfig(blur_strength=0.10, sharpness_boost=1.18, contrast_boost=1.08, unsharp_percent=140),
    "smoother": PresetConfig(blur_strength=0.42, sharpness_boost=0.96, contrast_boost=1.00, unsharp_percent=45),
}


def list_presets() -> tuple[str, ...]:
    return tuple(PRESETS.keys())


def prepare_image(image: Image.Image, target_size: int, preset: str) -> Image.Image:
    config = PRESETS[preset]
    scale_ratio = max(image.size) / max(target_size, 1)
    blur_radius = min(1.1, config.blur_strength * max(1.0, scale_ratio / 8.0))

    prepared = image.copy()
    if blur_radius > 0.01:
        prepared = prepared.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    if config.unsharp_percent > 0:
        prepared = prepared.filter(ImageFilter.UnsharpMask(radius=1.0, percent=config.unsharp_percent, threshold=2))

    resized = prepared.resize((target_size, target_size), Image.Resampling.BOX)
    resized = ImageEnhance.Sharpness(resized).enhance(config.sharpness_boost)
    return ImageEnhance.Contrast(resized).enhance(config.contrast_boost)
