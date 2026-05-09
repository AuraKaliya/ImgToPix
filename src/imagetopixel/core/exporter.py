from __future__ import annotations

from pathlib import Path

from .models import ProcessingOptions, ProcessingResult
from .pixelizer import build_preview


def resolve_target_dir(
    output_dir: str | Path,
    output_subdir: str | Path | None = None,
) -> Path:
    target_dir = Path(output_dir)
    if output_subdir:
        target_dir = target_dir / Path(output_subdir)
    return target_dir


def build_output_paths(
    result: ProcessingResult,
    output_dir: str | Path,
    options: ProcessingOptions,
    save_previews: bool = False,
    base_name: str | None = None,
    output_subdir: str | Path | None = None,
) -> list[Path]:
    target_dir = resolve_target_dir(output_dir, output_subdir)
    stem = base_name or result.source_path.stem
    output_paths: list[Path] = []

    for size in sorted(result.outputs):
        output_paths.append(target_dir / f"{stem}_{size}.png")
        if save_previews:
            output_paths.append(target_dir / f"{stem}_{size}_preview.png")

    return output_paths


def save_outputs(
    result: ProcessingResult,
    output_dir: str | Path,
    options: ProcessingOptions,
    save_previews: bool = False,
    base_name: str | None = None,
    output_subdir: str | Path | None = None,
) -> list[Path]:
    target_dir = resolve_target_dir(output_dir, output_subdir)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    stem = base_name or result.source_path.stem

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
