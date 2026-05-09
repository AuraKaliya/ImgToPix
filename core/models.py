from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image


TARGET_SIZES = (16, 32, 64)


@dataclass(frozen=True)
class ProcessingOptions:
    padding_mode: str = "edge"
    preset: str = "standard"
    sizes: tuple[int, ...] = TARGET_SIZES
    solid_color: tuple[int, int, int, int] = (0, 0, 0, 0)
    preview_scale: int = 12


@dataclass
class ProcessingResult:
    source_path: Path
    original: Image.Image
    squared: Image.Image
    outputs: dict[int, Image.Image] = field(default_factory=dict)
    padding: tuple[int, int, int, int] = (0, 0, 0, 0)
