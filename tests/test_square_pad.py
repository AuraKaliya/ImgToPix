from PIL import Image

from imagetopixel.core.square_pad import compute_padding, pad_to_square


def test_compute_padding_for_wide_image() -> None:
    assert compute_padding(10, 6) == (0, 2, 0, 2)


def test_pad_to_square_edge_mode_keeps_edge_colors() -> None:
    image = Image.new("RGBA", (2, 4))
    pixels = image.load()
    for y in range(4):
        pixels[0, y] = (255, 0, 0, 255)
        pixels[1, y] = (0, 0, 255, 255)

    squared, padding = pad_to_square(image, mode="edge")

    assert squared.size == (4, 4)
    assert padding == (1, 0, 1, 0)
    assert squared.getpixel((0, 0)) == (255, 0, 0, 255)
    assert squared.getpixel((3, 0)) == (0, 0, 255, 255)
