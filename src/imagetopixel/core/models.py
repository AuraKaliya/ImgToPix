from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


TARGET_SIZES = (16, 32, 64)
MASTER_SIZE = 16
DEFAULT_ALGORITHM = "majority"
DEFAULT_CONTOUR = "hybrid"


@dataclass(frozen=True)
class ProcessingOptions:
    padding_mode: str = "edge"
    algorithm: str = DEFAULT_ALGORITHM
    contour: str = DEFAULT_CONTOUR
    sizes: tuple[int, ...] = TARGET_SIZES
    solid_color: tuple[int, int, int, int] = (0, 0, 0, 0)
    preview_scale: int = 12
    mask_tolerance: int = 18
    coverage_strict: float = 0.50
    coverage_loose: float = 0.35
    hybrid_threshold: float = 0.30
    preserve_outline: bool = True
    outline_strength: float = 0.75
    palette_size: int = 16


@dataclass
class PaletteEntry:
    index: int
    rgba: tuple[int, int, int, int]
    pixel_count: int
    enabled: bool = True


@dataclass
class VariantResult:
    algorithm: str
    contour: str
    raw_master: Image.Image
    master: Image.Image
    outputs: dict[int, Image.Image] = field(default_factory=dict)
    palette_entries: list[PaletteEntry] = field(default_factory=list)
    palette_index_map: np.ndarray | None = None


@dataclass
class ContourVariantResult:
    contour: str
    mask: Image.Image
    variants: dict[str, VariantResult] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    source_path: Path
    original: Image.Image
    squared: Image.Image
    focused_square: Image.Image
    foreground_mask: Image.Image
    background_mode: str
    outputs: dict[int, Image.Image] = field(default_factory=dict)
    variants: dict[str, VariantResult] = field(default_factory=dict)
    contours: dict[str, ContourVariantResult] = field(default_factory=dict)
    selected_algorithm: str = DEFAULT_ALGORITHM
    selected_contour: str = DEFAULT_CONTOUR
    padding: tuple[int, int, int, int] = (0, 0, 0, 0)
