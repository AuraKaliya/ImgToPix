from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .image_loader import load_image
from .models import (
    DEFAULT_ALGORITHM,
    DEFAULT_CONTOUR,
    MASTER_SIZE,
    ContourVariantResult,
    PaletteEntry,
    ProcessingOptions,
    ProcessingResult,
    VariantResult,
)
from .preprocess import (
    build_contour_mask,
    build_master_sprite,
    extract_foreground_region,
    list_algorithms,
    list_contours,
)
from .square_pad import pad_to_square


def process_image(
    path: str | Path,
    options: ProcessingOptions,
    include_all_algorithms: bool = False,
) -> ProcessingResult:
    source_path = Path(path)
    original = load_image(source_path)
    squared, padding = pad_to_square(original, mode=options.padding_mode, fill_color=options.solid_color)
    foreground = extract_foreground_region(
        original,
        options=options,
        padding_mode=options.padding_mode,
        fill_color=options.solid_color,
    )

    selected_algorithm = options.algorithm if options.algorithm in list_algorithms() else DEFAULT_ALGORITHM
    selected_contour = options.contour if options.contour in list_contours() else DEFAULT_CONTOUR
    algorithms = list_algorithms() if include_all_algorithms else (selected_algorithm,)
    contours = list_contours() if include_all_algorithms else (selected_contour,)

    contour_results = {
        contour: build_contour_variant(
            foreground.image,
            foreground.hard_mask,
            contour=contour,
            algorithms=algorithms,
            sizes=options.sizes,
            options=options,
        )
        for contour in contours
    }

    selected_contour_result = contour_results[selected_contour]
    selected_variant = selected_contour_result.variants[selected_algorithm]
    return ProcessingResult(
        source_path=source_path,
        original=original,
        squared=squared,
        focused_square=apply_mask_to_image(foreground.image, foreground.hard_mask),
        foreground_mask=foreground.mask_preview,
        background_mode=foreground.background_mode,
        outputs=dict(selected_variant.outputs),
        variants=dict(selected_contour_result.variants),
        contours=contour_results,
        selected_algorithm=selected_algorithm,
        selected_contour=selected_contour,
        padding=padding,
    )


def build_contour_variant(
    image: Image.Image,
    source_mask: np.ndarray,
    contour: str,
    algorithms: tuple[str, ...],
    sizes: tuple[int, ...],
    options: ProcessingOptions,
) -> ContourVariantResult:
    contour_mask, scores = build_contour_mask(
        source_mask,
        contour=contour,
        options=options,
        target_size=MASTER_SIZE,
    )
    variants = {
        algorithm: build_variant(
            image,
            source_mask=source_mask,
            contour_mask=contour_mask,
            contour=contour,
            algorithm=algorithm,
            sizes=sizes,
            options=options,
        )
        for algorithm in algorithms
    }
    return ContourVariantResult(
        contour=contour,
        mask=mask_from_bool(contour_mask),
        variants=variants,
        scores=scores,
    )


def build_variant(
    image: Image.Image,
    source_mask: np.ndarray,
    contour_mask: np.ndarray,
    contour: str,
    algorithm: str,
    sizes: tuple[int, ...],
    options: ProcessingOptions,
) -> VariantResult:
    raw_master = build_master_sprite(
        image,
        source_mask=source_mask,
        contour_mask=contour_mask,
        algorithm=algorithm,
        options=options,
        target_size=MASTER_SIZE,
    )
    palette_entries, palette_index_map = analyze_palette(raw_master, target_size=options.palette_size)
    master = render_palette_master(palette_entries, palette_index_map)
    outputs = {size: render_output(master, size=size) for size in sizes}
    return VariantResult(
        algorithm=algorithm,
        contour=contour,
        raw_master=raw_master,
        master=master,
        outputs=outputs,
        palette_entries=palette_entries,
        palette_index_map=palette_index_map,
    )


def render_output(master: Image.Image, size: int) -> Image.Image:
    if master.size == (size, size):
        return master.copy()
    return master.resize((size, size), Image.Resampling.NEAREST)


def build_preview(image: Image.Image, scale: int) -> Image.Image:
    width, height = image.size
    return image.resize((width * scale, height * scale), Image.Resampling.NEAREST)


def mask_from_bool(mask: np.ndarray) -> Image.Image:
    rgba = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
    rgba[mask] = np.array([34, 92, 66, 255], dtype=np.uint8)
    return Image.fromarray(rgba, "RGBA")


def apply_mask_to_image(image: Image.Image, mask: np.ndarray) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    rgba[~mask] = np.array([0, 0, 0, 0], dtype=np.uint8)
    return Image.fromarray(rgba, "RGBA")


def rerender_variant_palette(variant: VariantResult, sizes: tuple[int, ...]) -> None:
    if variant.palette_index_map is None:
        return

    variant.master = render_palette_master(variant.palette_entries, variant.palette_index_map)
    variant.outputs = {size: render_output(variant.master, size=size) for size in sizes}


def analyze_palette(image: Image.Image, target_size: int) -> tuple[list[PaletteEntry], np.ndarray]:
    rgba = np.asarray(image.convert("RGBA"))
    index_map = np.full(rgba.shape[:2], -1, dtype=np.int16)
    opaque_mask = rgba[..., 3] > 0
    if not np.any(opaque_mask):
        return [], index_map

    opaque_colors = rgba[opaque_mask]
    unique_colors, inverse, counts = np.unique(opaque_colors, axis=0, return_inverse=True, return_counts=True)
    palette_target = min(max(1, target_size), max(1, len(unique_colors)))
    clusters = build_palette_clusters(unique_colors, counts, palette_target)

    color_to_palette: dict[tuple[int, int, int, int], int] = {}
    palette_entries: list[PaletteEntry] = []
    for index, cluster in enumerate(clusters):
        display_color = cluster_display_color(cluster)
        pixel_count = int(sum(item["count"] for item in cluster["members"]))
        palette_entries.append(
            PaletteEntry(
                index=index,
                rgba=display_color,
                pixel_count=pixel_count,
                enabled=True,
            )
        )
        for item in cluster["members"]:
            color_to_palette[tuple(int(value) for value in item["color"])] = index

    coords = np.argwhere(opaque_mask)
    for coord, color in zip(coords, opaque_colors, strict=False):
        index_map[coord[0], coord[1]] = color_to_palette[tuple(int(value) for value in color)]

    return palette_entries, index_map


def build_palette_clusters(
    unique_colors: np.ndarray,
    counts: np.ndarray,
    target_size: int,
) -> list[dict]:
    clusters = [
        {
            "mean": color.astype(np.float64),
            "members": [{"color": color.astype(np.uint8), "count": int(count)}],
        }
        for color, count in zip(unique_colors, counts, strict=False)
    ]

    while len(clusters) > target_size:
        best_i = 0
        best_j = 1
        best_distance = float("inf")
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                distance = np.linalg.norm(clusters[left]["mean"][:3] - clusters[right]["mean"][:3])
                if distance < best_distance:
                    best_distance = distance
                    best_i = left
                    best_j = right

        merged = merge_palette_clusters(clusters[best_i], clusters[best_j])
        clusters[best_i] = merged
        del clusters[best_j]

    return sorted(
        clusters,
        key=lambda cluster: sum(item["count"] for item in cluster["members"]),
        reverse=True,
    )


def merge_palette_clusters(left: dict, right: dict) -> dict:
    members = [*left["members"], *right["members"]]
    total = sum(item["count"] for item in members)
    weighted = sum(item["color"].astype(np.float64) * item["count"] for item in members) / max(total, 1)
    return {"mean": weighted, "members": members}


def cluster_display_color(cluster: dict) -> tuple[int, int, int, int]:
    mean = cluster["mean"]
    best_member = min(
        cluster["members"],
        key=lambda item: (
            np.linalg.norm(item["color"][:3].astype(np.float64) - mean[:3]),
            -item["count"],
        ),
    )
    return tuple(int(value) for value in best_member["color"])


def render_palette_master(palette_entries: list[PaletteEntry], palette_index_map: np.ndarray) -> Image.Image:
    height, width = palette_index_map.shape
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    palette_by_index = {entry.index: entry for entry in palette_entries}
    enabled_entries = [entry for entry in palette_entries if entry.enabled]

    for y in range(height):
        for x in range(width):
            palette_index = int(palette_index_map[y, x])
            if palette_index < 0:
                continue

            entry = palette_by_index[palette_index]
            if entry.enabled:
                rgba[y, x] = np.array(entry.rgba, dtype=np.uint8)
                continue

            replacement = nearest_enabled_entry(entry, enabled_entries)
            if replacement is None:
                continue
            rgba[y, x] = np.array(replacement.rgba, dtype=np.uint8)

    return Image.fromarray(rgba, "RGBA")


def nearest_enabled_entry(entry: PaletteEntry, enabled_entries: list[PaletteEntry]) -> PaletteEntry | None:
    if not enabled_entries:
        return None

    source = np.array(entry.rgba[:3], dtype=np.float64)
    return min(
        enabled_entries,
        key=lambda candidate: np.linalg.norm(np.array(candidate.rgba[:3], dtype=np.float64) - source),
    )
