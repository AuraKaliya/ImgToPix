from __future__ import annotations

from pathlib import Path

from PIL import Image

from .image_loader import load_image
from .models import ProcessingOptions, ProcessingResult
from .preprocess import prepare_image
from .square_pad import pad_to_square


def process_image(path: str | Path, options: ProcessingOptions) -> ProcessingResult:
    source_path = Path(path)
    original = load_image(source_path)
    squared, padding = pad_to_square(original, mode=options.padding_mode, fill_color=options.solid_color)

    outputs = {
        size: pixelize(squared, size=size, preset=options.preset)
        for size in options.sizes
    }
    return ProcessingResult(
        source_path=source_path,
        original=original,
        squared=squared,
        outputs=outputs,
        padding=padding,
    )


def pixelize(image: Image.Image, size: int, preset: str) -> Image.Image:
    return prepare_image(image, target_size=size, preset=preset)


def build_preview(image: Image.Image, scale: int) -> Image.Image:
    width, height = image.size
    return image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
