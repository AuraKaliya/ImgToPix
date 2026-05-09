from __future__ import annotations

import numpy as np
from PIL import Image


def compute_padding(width: int, height: int) -> tuple[int, int, int, int]:
    if width == height:
        return (0, 0, 0, 0)

    if width < height:
        delta = height - width
        left = delta // 2
        right = delta - left
        return (left, 0, right, 0)

    delta = width - height
    top = delta // 2
    bottom = delta - top
    return (0, top, 0, bottom)


def pad_to_square(
    image: Image.Image,
    mode: str = "edge",
    fill_color: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    width, height = image.size
    padding = compute_padding(width, height)

    if padding == (0, 0, 0, 0):
        return image.copy(), padding

    left, top, right, bottom = padding

    if mode == "solid":
        canvas = Image.new("RGBA", (width + left + right, height + top + bottom), fill_color)
        canvas.paste(image, (left, top))
        return canvas, padding

    np_mode = "edge" if mode == "edge" else "reflect"
    array = np.array(image)
    padded = np.pad(
        array,
        ((top, bottom), (left, right), (0, 0)),
        mode=np_mode,
    )
    return Image.fromarray(padded, "RGBA"), padding
