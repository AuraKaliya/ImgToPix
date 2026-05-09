from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from .models import MASTER_SIZE


@dataclass(frozen=True)
class AlgorithmConfig:
    label: str
    description: str
    blur_strength: float
    sharpness_boost: float
    contrast_boost: float
    unsharp_percent: int
    sampler: str


ALGORITHMS: dict[str, AlgorithmConfig] = {
    "majority": AlgorithmConfig(
        label="Majority",
        description="Block vote that favors solid sprite shapes.",
        blur_strength=0.10,
        sharpness_boost=1.08,
        contrast_boost=1.06,
        unsharp_percent=120,
        sampler="mode",
    ),
    "median": AlgorithmConfig(
        label="Median",
        description="Balanced pooling that softens noisy anti-aliasing.",
        blur_strength=0.16,
        sharpness_boost=1.02,
        contrast_boost=1.03,
        unsharp_percent=80,
        sampler="median",
    ),
    "center": AlgorithmConfig(
        label="Center",
        description="Crisp center-pick sampling for hard pixel edges.",
        blur_strength=0.0,
        sharpness_boost=1.16,
        contrast_boost=1.08,
        unsharp_percent=140,
        sampler="center",
    ),
}


def list_algorithms() -> tuple[str, ...]:
    return tuple(ALGORITHMS.keys())


def algorithm_label(name: str) -> str:
    return ALGORITHMS[name].label


def algorithm_description(name: str) -> str:
    return ALGORITHMS[name].description


def trim_uniform_border(image: Image.Image, tolerance: int = 12, alpha_threshold: int = 8) -> Image.Image:
    array = np.asarray(image.convert("RGBA"))
    alpha = array[..., 3]

    opaque_coords = np.argwhere(alpha > alpha_threshold)
    if opaque_coords.size > 0 and np.any(alpha <= alpha_threshold):
        top, left = opaque_coords.min(axis=0)
        bottom, right = opaque_coords.max(axis=0)
        return image.crop((left, top, right + 1, bottom + 1))

    corners = np.array(
        [
            array[0, 0],
            array[0, -1],
            array[-1, 0],
            array[-1, -1],
        ],
        dtype=np.int16,
    )
    background = np.median(corners, axis=0).astype(np.int16)
    if np.max(np.abs(corners - background)) > tolerance:
        return image.copy()

    diff = np.max(np.abs(array.astype(np.int16) - background), axis=2)
    coords = np.argwhere(diff > tolerance)
    if coords.size == 0:
        return image.copy()

    top, left = coords.min(axis=0)
    bottom, right = coords.max(axis=0)
    return image.crop((left, top, right + 1, bottom + 1))


def build_master_sprite(image: Image.Image, algorithm: str, target_size: int = MASTER_SIZE) -> Image.Image:
    config = ALGORITHMS[algorithm]
    scale_ratio = max(image.size) / max(target_size, 1)
    blur_radius = min(1.1, config.blur_strength * max(1.0, scale_ratio / 8.0))

    prepared = image.copy()
    if blur_radius > 0.01:
        prepared = prepared.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    if config.unsharp_percent > 0:
        prepared = prepared.filter(ImageFilter.UnsharpMask(radius=1.0, percent=config.unsharp_percent, threshold=2))

    prepared = ImageEnhance.Sharpness(prepared).enhance(config.sharpness_boost)
    prepared = ImageEnhance.Contrast(prepared).enhance(config.contrast_boost)
    return downsample_image(prepared, target_size=target_size, sampler=config.sampler)


def downsample_image(image: Image.Image, target_size: int, sampler: str) -> Image.Image:
    array = np.asarray(image.convert("RGBA"))
    reduced = np.zeros((target_size, target_size, 4), dtype=np.uint8)

    x_edges = np.linspace(0, array.shape[1], target_size + 1)
    y_edges = np.linspace(0, array.shape[0], target_size + 1)

    for target_y in range(target_size):
        y0 = int(np.floor(y_edges[target_y]))
        y1 = int(np.floor(y_edges[target_y + 1]))
        if y1 <= y0:
            y1 = min(array.shape[0], y0 + 1)
        if target_y == target_size - 1:
            y1 = array.shape[0]

        for target_x in range(target_size):
            x0 = int(np.floor(x_edges[target_x]))
            x1 = int(np.floor(x_edges[target_x + 1]))
            if x1 <= x0:
                x1 = min(array.shape[1], x0 + 1)
            if target_x == target_size - 1:
                x1 = array.shape[1]

            block = array[y0:y1, x0:x1]
            reduced[target_y, target_x] = sample_block(block, sampler=sampler)

    return Image.fromarray(reduced, "RGBA")


def sample_block(block: np.ndarray, sampler: str) -> np.ndarray:
    if sampler == "center":
        return block[block.shape[0] // 2, block.shape[1] // 2]

    if sampler == "median":
        return np.median(block, axis=(0, 1)).round().astype(np.uint8)

    flat = block.reshape(-1, block.shape[-1])
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    max_count = counts.max()
    center_color = flat[len(flat) // 2]
    center_match = np.all(colors == center_color, axis=1) & (counts == max_count)
    if np.any(center_match):
        return center_color.astype(np.uint8)

    return colors[np.argmax(counts)].astype(np.uint8)
