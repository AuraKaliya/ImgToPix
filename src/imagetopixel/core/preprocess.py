from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from .models import MASTER_SIZE, ProcessingOptions
from .square_pad import compute_padding


@dataclass(frozen=True)
class AlgorithmConfig:
    label: str
    description: str
    blur_strength: float
    sharpness_boost: float
    contrast_boost: float
    unsharp_percent: int
    sampler: str


@dataclass(frozen=True)
class ContourConfig:
    label: str
    description: str
    coverage_threshold: float
    center_required: bool = False
    hybrid_threshold: float | None = None


@dataclass(frozen=True)
class ForegroundRegion:
    image: Image.Image
    mask_preview: Image.Image
    hard_mask: np.ndarray
    background_mode: str


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


CONTOURS: dict[str, ContourConfig] = {
    "coverage-50": ContourConfig(
        label="Coverage 50%",
        description="Balanced silhouette using a 50% foreground threshold.",
        coverage_threshold=0.50,
    ),
    "coverage-35": ContourConfig(
        label="Coverage 35%",
        description="Looser silhouette that preserves thinner protrusions.",
        coverage_threshold=0.35,
    ),
    "center-hit": ContourConfig(
        label="Center Hit",
        description="Sharp silhouette based on whether the cell center stays inside the item.",
        coverage_threshold=0.0,
        center_required=True,
    ),
    "hybrid": ContourConfig(
        label="Hybrid",
        description="Center-first contour with a fallback coverage threshold for thin details.",
        coverage_threshold=0.50,
        hybrid_threshold=0.30,
    ),
}


def list_algorithms() -> tuple[str, ...]:
    return tuple(ALGORITHMS.keys())


def list_contours() -> tuple[str, ...]:
    return tuple(CONTOURS.keys())


def algorithm_label(name: str) -> str:
    return ALGORITHMS[name].label


def contour_label(name: str) -> str:
    return CONTOURS[name].label


def algorithm_description(name: str) -> str:
    return ALGORITHMS[name].description


def contour_description(name: str) -> str:
    return CONTOURS[name].description


def extract_foreground_region(
    image: Image.Image,
    options: ProcessingOptions,
    padding_mode: str = "edge",
    fill_color: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> ForegroundRegion:
    rgba = np.asarray(image.convert("RGBA"))
    hard_mask, background_mode = detect_foreground_mask(
        rgba,
        solid_tolerance=options.mask_tolerance,
    )
    hard_mask = clean_source_mask(hard_mask)

    if not np.any(hard_mask):
        hard_mask = np.ones(rgba.shape[:2], dtype=bool)
        background_mode = "fallback"

    top, left, bottom, right = bounding_box_from_mask(hard_mask)
    cropped_image = image.crop((left, top, right + 1, bottom + 1))
    cropped_mask = hard_mask[top : bottom + 1, left : right + 1]

    focused_image = pad_image_to_square(cropped_image, padding_mode=padding_mode, fill_color=fill_color)
    focused_mask = pad_mask_to_square(cropped_mask)
    focused_mask = clean_source_mask(focused_mask)

    return ForegroundRegion(
        image=focused_image,
        mask_preview=mask_to_preview_image(focused_mask),
        hard_mask=focused_mask,
        background_mode=background_mode,
    )


def detect_foreground_mask(rgba: np.ndarray, alpha_threshold: int = 8, solid_tolerance: int = 18) -> tuple[np.ndarray, str]:
    alpha = rgba[..., 3]
    opaque_mask = alpha > alpha_threshold
    has_transparency = np.any(alpha <= alpha_threshold)
    has_opaque = np.any(opaque_mask)
    if has_transparency and has_opaque:
        return opaque_mask, "alpha"

    background = estimate_background_color(rgba[..., :3], tolerance=solid_tolerance)
    if background is not None:
        diff = np.max(np.abs(rgba[..., :3].astype(np.int16) - background), axis=2)
        similar = diff <= solid_tolerance
        background_mask = flood_fill_from_border(similar)
        hard_mask = ~background_mask
        if np.any(hard_mask):
            return hard_mask, "solid"

    return np.ones(rgba.shape[:2], dtype=bool), "fallback"


def border_pixels(rgb: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    segments = [rgb[0, :], rgb[-1, :]]
    if height > 2:
        segments.extend([rgb[1:-1, 0], rgb[1:-1, -1]])
    return np.concatenate(segments, axis=0)


def corner_pixels(rgb: np.ndarray) -> np.ndarray:
    return np.array(
        [
            rgb[0, 0],
            rgb[0, -1],
            rgb[-1, 0],
            rgb[-1, -1],
        ],
        dtype=np.int16,
    )


def estimate_background_color(rgb: np.ndarray, tolerance: int) -> np.ndarray | None:
    corners = corner_pixels(rgb)
    best_group: np.ndarray | None = None

    for index in range(len(corners)):
        deltas = np.max(np.abs(corners - corners[index]), axis=1)
        group = corners[deltas <= tolerance]
        if best_group is None or len(group) > len(best_group):
            best_group = group

    if best_group is None or len(best_group) < 2:
        return None

    return np.median(best_group, axis=0).astype(np.int16)


def flood_fill_from_border(similar: np.ndarray) -> np.ndarray:
    height, width = similar.shape
    visited = np.zeros_like(similar, dtype=bool)
    stack: list[tuple[int, int]] = []

    for x in range(width):
        if similar[0, x]:
            stack.append((0, x))
        if similar[height - 1, x]:
            stack.append((height - 1, x))
    for y in range(1, height - 1):
        if similar[y, 0]:
            stack.append((y, 0))
        if similar[y, width - 1]:
            stack.append((y, width - 1))

    while stack:
        y, x = stack.pop()
        if visited[y, x] or not similar[y, x]:
            continue

        visited[y, x] = True
        if y > 0:
            stack.append((y - 1, x))
        if y + 1 < height:
            stack.append((y + 1, x))
        if x > 0:
            stack.append((y, x - 1))
        if x + 1 < width:
            stack.append((y, x + 1))

    return visited


def clean_source_mask(mask: np.ndarray) -> np.ndarray:
    if not np.any(mask):
        return mask.astype(bool)

    components = connected_components(mask)
    if not components:
        return mask.astype(bool)

    largest = max(len(component) for component in components)
    min_keep = max(4, int(round(largest * 0.12)))
    kept = np.zeros_like(mask, dtype=bool)
    for component in components:
        if len(component) >= min_keep:
            rows, cols = zip(*component)
            kept[list(rows), list(cols)] = True

    if not np.any(kept):
        rows, cols = zip(*max(components, key=len))
        kept[list(rows), list(cols)] = True

    return fill_small_holes(kept)


def bounding_box_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    coords = np.argwhere(mask)
    if coords.size == 0:
        return (0, 0, mask.shape[0] - 1, mask.shape[1] - 1)

    top, left = coords.min(axis=0)
    bottom, right = coords.max(axis=0)
    return int(top), int(left), int(bottom), int(right)


def pad_image_to_square(
    image: Image.Image,
    padding_mode: str,
    fill_color: tuple[int, int, int, int],
) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = compute_padding(width, height)
    if left == top == right == bottom == 0:
        return image.copy()

    if padding_mode == "solid":
        canvas = Image.new("RGBA", (width + left + right, height + top + bottom), fill_color)
        canvas.paste(image, (left, top))
        return canvas

    array = np.asarray(image.convert("RGBA"))
    np_mode = "edge" if padding_mode == "edge" else "reflect"
    if np_mode == "reflect" and (height == 1 or width == 1):
        np_mode = "edge"
    padded = np.pad(array, ((top, bottom), (left, right), (0, 0)), mode=np_mode)
    return Image.fromarray(padded.astype(np.uint8), "RGBA")


def pad_mask_to_square(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    left, top, right, bottom = compute_padding(width, height)
    if left == top == right == bottom == 0:
        return mask.astype(bool)

    # The square padding area is still background, so the mask must stay empty there.
    return np.pad(mask.astype(bool), ((top, bottom), (left, right)), mode="constant", constant_values=False)


def build_contour_mask(
    mask: np.ndarray,
    contour: str,
    options: ProcessingOptions,
    target_size: int = MASTER_SIZE,
) -> tuple[np.ndarray, dict[str, float]]:
    config = contour_config_for_options(contour, options)
    reduced = np.zeros((target_size, target_size), dtype=bool)
    x_edges = np.linspace(0, mask.shape[1], target_size + 1)
    y_edges = np.linspace(0, mask.shape[0], target_size + 1)

    for target_y in range(target_size):
        y0, y1 = slice_bounds(y_edges, target_y, mask.shape[0], target_size)
        for target_x in range(target_size):
            x0, x1 = slice_bounds(x_edges, target_x, mask.shape[1], target_size)
            block = mask[y0:y1, x0:x1]
            coverage = float(block.mean())
            cy, cx = block.shape[0] // 2, block.shape[1] // 2
            center_hit = bool(block[cy, cx])

            if config.center_required:
                keep = center_hit
            elif config.hybrid_threshold is not None:
                keep = center_hit or coverage >= config.hybrid_threshold
            else:
                keep = coverage >= config.coverage_threshold

            reduced[target_y, target_x] = keep

    cleaned = clean_contour_mask(reduced)
    scores = score_contour_mask(cleaned)
    return cleaned, scores


def build_master_sprite(
    image: Image.Image,
    source_mask: np.ndarray,
    contour_mask: np.ndarray,
    algorithm: str,
    options: ProcessingOptions,
    target_size: int = MASTER_SIZE,
) -> Image.Image:
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
    return downsample_image(
        prepared,
        target_size=target_size,
        sampler=config.sampler,
        source_mask=source_mask,
        contour_mask=contour_mask,
        preserve_outline=options.preserve_outline,
        outline_strength=options.outline_strength,
    )


def downsample_image(
    image: Image.Image,
    target_size: int,
    sampler: str,
    source_mask: np.ndarray | None = None,
    contour_mask: np.ndarray | None = None,
    preserve_outline: bool = True,
    outline_strength: float = 0.75,
) -> Image.Image:
    array = np.asarray(image.convert("RGBA"))
    reduced = np.zeros((target_size, target_size, 4), dtype=np.uint8)
    source_boundary_mask = boundary_mask(source_mask) if source_mask is not None else None

    x_edges = np.linspace(0, array.shape[1], target_size + 1)
    y_edges = np.linspace(0, array.shape[0], target_size + 1)

    for target_y in range(target_size):
        y0, y1 = slice_bounds(y_edges, target_y, array.shape[0], target_size)
        for target_x in range(target_size):
            x0, x1 = slice_bounds(x_edges, target_x, array.shape[1], target_size)
            if contour_mask is not None and not contour_mask[target_y, target_x]:
                reduced[target_y, target_x] = np.array([0, 0, 0, 0], dtype=np.uint8)
                continue

            block = array[y0:y1, x0:x1]
            block_mask = source_mask[y0:y1, x0:x1] if source_mask is not None else None
            boundary_block_mask = (
                source_boundary_mask[y0:y1, x0:x1] if source_boundary_mask is not None else None
            )
            reduced[target_y, target_x] = sample_block(
                block,
                sampler=sampler,
                source_mask=block_mask,
                boundary_mask=boundary_block_mask,
                prefer_boundary=bool(
                    preserve_outline
                    and contour_mask is not None
                    and is_boundary_cell(contour_mask, target_y, target_x)
                ),
                outline_strength=outline_strength,
            )

    return Image.fromarray(reduced, "RGBA")


def sample_block(
    block: np.ndarray,
    sampler: str,
    source_mask: np.ndarray | None = None,
    boundary_mask: np.ndarray | None = None,
    prefer_boundary: bool = False,
    outline_strength: float = 0.75,
) -> np.ndarray:
    center_y, center_x = block.shape[0] // 2, block.shape[1] // 2

    if source_mask is not None and np.any(source_mask):
        pixels = block[source_mask]
    else:
        pixels = block.reshape(-1, block.shape[-1])
        source_mask = None

    boundary_pixels: np.ndarray | None = None
    if (
        prefer_boundary
        and boundary_mask is not None
        and np.any(boundary_mask)
    ):
        boundary_pixels = block[boundary_mask]

    if sampler == "center":
        if boundary_pixels is not None and len(boundary_pixels) > 0:
            if source_mask is not None and boundary_mask is not None and boundary_mask[center_y, center_x]:
                return block[center_y, center_x].astype(np.uint8)
            return nearest_pixel_to_center(block, boundary_mask).astype(np.uint8)

        if source_mask is None or source_mask[center_y, center_x]:
            return block[center_y, center_x].astype(np.uint8)

        return nearest_pixel_to_center(block, source_mask).astype(np.uint8)

    if sampler == "median":
        base = np.median(pixels, axis=0).round()
        if boundary_pixels is None:
            return base.astype(np.uint8)
        edge = np.median(boundary_pixels, axis=0).round()
        return blend_colors(base, edge, outline_strength)

    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    max_count = counts.max()
    center_color = block[center_y, center_x]
    center_match = np.all(colors == center_color, axis=1) & (counts == max_count)
    if np.any(center_match):
        base = center_color.astype(np.float32)
    else:
        base = colors[np.argmax(counts)].astype(np.float32)

    if boundary_pixels is None:
        return base.astype(np.uint8)

    edge = mode_color(boundary_pixels).astype(np.float32)
    return blend_colors(base, edge, outline_strength)


def contour_config_for_options(contour: str, options: ProcessingOptions) -> ContourConfig:
    base = CONTOURS[contour]
    if contour == "coverage-50":
        return ContourConfig(base.label, base.description, options.coverage_strict)
    if contour == "coverage-35":
        return ContourConfig(base.label, base.description, options.coverage_loose)
    if contour == "hybrid":
        return ContourConfig(
            base.label,
            base.description,
            options.coverage_strict,
            center_required=False,
            hybrid_threshold=options.hybrid_threshold,
        )
    return base


def nearest_pixel_to_center(block: np.ndarray, mask: np.ndarray) -> np.ndarray:
    center_y, center_x = block.shape[0] // 2, block.shape[1] // 2
    coords = np.argwhere(mask)
    distances = (coords[:, 0] - center_y) ** 2 + (coords[:, 1] - center_x) ** 2
    nearest = coords[np.argmin(distances)]
    return block[nearest[0], nearest[1]]


def mode_color(pixels: np.ndarray) -> np.ndarray:
    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    return colors[np.argmax(counts)].astype(np.uint8)


def blend_colors(base: np.ndarray, edge: np.ndarray, strength: float) -> np.ndarray:
    clipped = min(max(strength, 0.0), 1.0)
    blended = base * (1.0 - clipped) + edge * clipped
    return np.round(blended).astype(np.uint8)


def boundary_mask(mask: np.ndarray | None) -> np.ndarray | None:
    if mask is None:
        return None

    height, width = mask.shape
    boundary = np.zeros_like(mask, dtype=bool)
    for y in range(height):
        for x in range(width):
            if not mask[y, x]:
                continue
            for ny, nx in orthogonal_neighbors(y, x, height, width):
                if not mask[ny, nx]:
                    boundary[y, x] = True
                    break
    return boundary


def is_boundary_cell(mask: np.ndarray, y: int, x: int) -> bool:
    if not mask[y, x]:
        return False
    height, width = mask.shape
    for ny, nx in orthogonal_neighbors(y, x, height, width):
        if not mask[ny, nx]:
            return True
    return y == 0 or x == 0 or y == height - 1 or x == width - 1


def orthogonal_neighbors(y: int, x: int, height: int, width: int) -> list[tuple[int, int]]:
    neighbors: list[tuple[int, int]] = []
    if y > 0:
        neighbors.append((y - 1, x))
    if y + 1 < height:
        neighbors.append((y + 1, x))
    if x > 0:
        neighbors.append((y, x - 1))
    if x + 1 < width:
        neighbors.append((y, x + 1))
    return neighbors


def slice_bounds(edges: np.ndarray, index: int, upper_bound: int, target_size: int) -> tuple[int, int]:
    start = int(np.floor(edges[index]))
    end = int(np.floor(edges[index + 1]))
    if end <= start:
        end = min(upper_bound, start + 1)
    if index == target_size - 1:
        end = upper_bound
    return start, end


def clean_contour_mask(mask: np.ndarray) -> np.ndarray:
    cleaned = remove_tiny_islands(mask, max_island_size=1)
    cleaned = fill_small_holes(cleaned)
    return preserve_main_components(cleaned)


def remove_tiny_islands(mask: np.ndarray, max_island_size: int) -> np.ndarray:
    cleaned = mask.copy()
    for component in connected_components(mask):
        if len(component) <= max_island_size:
            rows, cols = zip(*component)
            cleaned[list(rows), list(cols)] = False
    return cleaned


def preserve_main_components(mask: np.ndarray) -> np.ndarray:
    components = connected_components(mask)
    if not components:
        return mask

    largest = max(len(component) for component in components)
    min_keep = max(2, int(round(largest * 0.18)))
    kept = np.zeros_like(mask, dtype=bool)
    for component in components:
        if len(component) >= min_keep:
            rows, cols = zip(*component)
            kept[list(rows), list(cols)] = True

    if not np.any(kept):
        rows, cols = zip(*max(components, key=len))
        kept[list(rows), list(cols)] = True
    return kept


def fill_small_holes(mask: np.ndarray) -> np.ndarray:
    filled = mask.copy()
    height, width = mask.shape
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if mask[y, x]:
                continue
            neighborhood = mask[y - 1 : y + 2, x - 1 : x + 2]
            if int(neighborhood.sum()) >= 7:
                filled[y, x] = True
    return filled


def score_contour_mask(mask: np.ndarray) -> dict[str, float]:
    components = connected_components(mask)
    return {
        "fill_ratio": float(mask.mean()),
        "component_count": float(len(components)),
        "island_pixels": float(sum(len(component) for component in components if len(component) == 1)),
    }


def connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            component: list[tuple[int, int]] = []
            while stack:
                cy, cx = stack.pop()
                component.append((cy, cx))
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if (ny == cy and nx == cx) or visited[ny, nx] or not mask[ny, nx]:
                            continue
                        visited[ny, nx] = True
                        stack.append((ny, nx))

            components.append(component)

    return components


def mask_to_preview_image(mask: np.ndarray) -> Image.Image:
    rgba = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
    rgba[mask] = np.array([34, 92, 66, 255], dtype=np.uint8)
    return Image.fromarray(rgba, "RGBA")
