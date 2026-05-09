from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


SUPPORTED_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.webp)"


def load_image(path: str | Path) -> Image.Image:
    image_path = Path(path)
    with Image.open(image_path) as image:
        normalized = ImageOps.exif_transpose(image)
        return normalized.convert("RGBA")
