from __future__ import annotations

from pathlib import Path

from .models import ProcessingOptions, ProcessingResult
from .pixelizer import build_preview


def save_outputs(
    result: ProcessingResult,
    output_dir: str | Path,
    options: ProcessingOptions,
    save_previews: bool = False,
) -> list[Path]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    stem = result.source_path.stem

    for size, image in sorted(result.outputs.items()):
        pixel_path = target_dir / f"{stem}_{size}.png"
        image.save(pixel_path)
        saved_paths.append(pixel_path)

        if save_previews:
            preview = build_preview(image, scale=options.preview_scale)
            preview_path = target_dir / f"{stem}_{size}_preview.png"
            preview.save(preview_path)
            saved_paths.append(preview_path)

    return saved_paths
