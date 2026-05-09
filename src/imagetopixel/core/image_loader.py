from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
SUPPORTED_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.webp)"


def is_supported_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def load_image(path: str | Path) -> Image.Image:
    image_path = Path(path)
    with Image.open(image_path) as image:
        normalized = ImageOps.exif_transpose(image)
        return normalized.convert("RGBA")
