from __future__ import annotations

from pathlib import Path

from PIL import Image

from .image_loader import load_image
from .models import DEFAULT_ALGORITHM, MASTER_SIZE, ProcessingOptions, ProcessingResult, VariantResult
from .preprocess import build_master_sprite, list_algorithms, trim_uniform_border
from .square_pad import pad_to_square


def process_image(
    path: str | Path,
    options: ProcessingOptions,
    include_all_algorithms: bool = False,
) -> ProcessingResult:
    source_path = Path(path)
    original = load_image(source_path)
    squared, padding = pad_to_square(original, mode=options.padding_mode, fill_color=options.solid_color)
    focused = trim_uniform_border(squared)
    focused_square, _ = pad_to_square(focused, mode=options.padding_mode, fill_color=options.solid_color)

    selected_algorithm = options.algorithm if options.algorithm in list_algorithms() else DEFAULT_ALGORITHM
    algorithms = list_algorithms() if include_all_algorithms else (selected_algorithm,)
    variants = {
        algorithm: build_variant(focused_square, algorithm=algorithm, sizes=options.sizes)
        for algorithm in algorithms
    }
    selected_variant = variants[selected_algorithm]
    return ProcessingResult(
        source_path=source_path,
        original=original,
        squared=squared,
        outputs=selected_variant.outputs,
        variants=variants,
        selected_algorithm=selected_algorithm,
        padding=padding,
    )


def build_variant(image: Image.Image, algorithm: str, sizes: tuple[int, ...]) -> VariantResult:
    master = build_master_sprite(image, algorithm=algorithm, target_size=MASTER_SIZE)
    outputs = {size: render_output(master, size=size) for size in sizes}
    return VariantResult(algorithm=algorithm, master=master, outputs=outputs)


def render_output(master: Image.Image, size: int) -> Image.Image:
    if master.size == (size, size):
        return master.copy()
    return master.resize((size, size), Image.Resampling.NEAREST)


def build_preview(image: Image.Image, scale: int) -> Image.Image:
    width, height = image.size
    return image.resize((width * scale, height * scale), Image.Resampling.NEAREST)
