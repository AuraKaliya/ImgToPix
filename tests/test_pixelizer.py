from pathlib import Path

from PIL import Image

from imagetopixel.core.models import MASTER_SIZE, PaletteEntry, ProcessingOptions, VariantResult
from imagetopixel.core.pixelizer import analyze_palette, process_image, render_output, rerender_variant_palette
from imagetopixel.core.preprocess import list_algorithms, list_contours


def test_process_image_outputs_expected_sizes(tmp_path: Path) -> None:
    image = Image.new("RGBA", (80, 60), (128, 200, 90, 255))
    source = tmp_path / "source.png"
    image.save(source)

    result = process_image(source, ProcessingOptions())

    assert result.squared.size == (80, 80)
    assert result.focused_square.size[0] == result.focused_square.size[1]
    assert result.background_mode in {"alpha", "solid", "fallback"}
    assert set(result.outputs.keys()) == {16, 32, 64}
    assert result.outputs[16].size == (16, 16)
    assert result.outputs[32].size == (32, 32)
    assert result.outputs[64].size == (64, 64)
    assert result.outputs[32].tobytes() == result.outputs[16].resize((32, 32), Image.Resampling.NEAREST).tobytes()
    assert result.outputs[64].tobytes() == result.outputs[16].resize((64, 64), Image.Resampling.NEAREST).tobytes()


def test_process_image_can_return_all_algorithm_variants(tmp_path: Path) -> None:
    image = Image.new("RGBA", (48, 48), (255, 255, 255, 255))
    pixels = image.load()
    for x in range(12, 36):
        for y in range(8, 40):
            pixels[x, y] = (20 + x, 120 + y, 60, 255)

    source = tmp_path / "source.png"
    image.save(source)

    result = process_image(
        source,
        ProcessingOptions(algorithm="median", contour="hybrid"),
        include_all_algorithms=True,
    )

    assert result.selected_algorithm == "median"
    assert result.selected_contour == "hybrid"
    assert set(result.contours.keys()) == set(list_contours())
    assert set(result.contours["hybrid"].variants.keys()) == set(list_algorithms())
    assert result.contours["hybrid"].variants["median"].master.size == (MASTER_SIZE, MASTER_SIZE)
    assert result.outputs[16].tobytes() == result.contours["hybrid"].variants["median"].outputs[16].tobytes()


def test_process_image_extracts_alpha_mask_and_transparent_background(tmp_path: Path) -> None:
    image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    pixels = image.load()
    for x in range(10, 38):
        for y in range(6, 42):
            pixels[x, y] = (0, 170, 60, 255)

    source = tmp_path / "alpha_item.png"
    image.save(source)

    result = process_image(source, ProcessingOptions(contour="coverage-35"))

    assert result.background_mode == "alpha"
    assert result.foreground_mask.getbbox() is not None
    assert result.outputs[16].getbbox() is not None


def test_process_image_mask_padding_keeps_added_square_area_empty(tmp_path: Path) -> None:
    image = Image.new("RGBA", (96, 48), (255, 255, 255, 255))
    pixels = image.load()
    for x in range(18, 78):
        for y in range(12, 28):
            pixels[x, y] = (30, 140, 70, 255)

    source = tmp_path / "wide_item.png"
    image.save(source)

    result = process_image(source, ProcessingOptions(padding_mode="edge"))
    bbox = result.foreground_mask.getbbox()

    assert bbox is not None
    left, top, right, bottom = bbox
    assert top > 0
    assert bottom < result.foreground_mask.height


def test_process_image_preserves_outline_when_enabled(tmp_path: Path) -> None:
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    pixels = image.load()
    for x in range(12, 52):
        for y in range(10, 50):
            pixels[x, y] = (80, 160, 70, 255)
    for x in range(12, 52):
        pixels[x, 10] = (20, 70, 40, 255)
        pixels[x, 49] = (20, 70, 40, 255)
    for y in range(10, 50):
        pixels[12, y] = (20, 70, 40, 255)
        pixels[51, y] = (20, 70, 40, 255)

    source = tmp_path / "outlined.png"
    image.save(source)

    result = process_image(
        source,
        ProcessingOptions(preserve_outline=True, outline_strength=1.0),
    )

    output = result.outputs[16]
    border_pixels = []
    for x in range(16):
        for y in range(16):
            pixel = output.getpixel((x, y))
            if pixel[3] == 0:
                continue
            if x in {0, 15} or y in {0, 15}:
                border_pixels.append(pixel)
    assert border_pixels
    assert any(pixel[1] < 120 for pixel in border_pixels)


def test_analyze_palette_merges_colors_to_target_count() -> None:
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    pixels = image.load()
    colors = [
        (220, 30, 30, 255),
        (210, 40, 40, 255),
        (30, 220, 30, 255),
        (40, 210, 40, 255),
        (30, 30, 220, 255),
        (40, 40, 210, 255),
    ]
    index = 0
    for y in range(4):
        for x in range(4):
            pixels[x, y] = colors[index % len(colors)]
            index += 1

    palette_entries, palette_index_map = analyze_palette(image, target_size=3)

    assert len(palette_entries) == 3
    assert palette_index_map.shape == (4, 4)


def test_rerender_variant_palette_updates_outputs_when_color_disabled() -> None:
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    pixels = image.load()
    pixels[0, 0] = (200, 40, 40, 255)
    pixels[1, 0] = (200, 40, 40, 255)
    pixels[0, 1] = (40, 200, 40, 255)
    pixels[1, 1] = (40, 200, 40, 255)

    palette_entries, palette_index_map = analyze_palette(image, target_size=2)
    master = image.copy()
    variant = VariantResult(
        algorithm="majority",
        contour="hybrid",
        raw_master=master,
        master=master,
        outputs={16: render_output(master, 16)},
        palette_entries=palette_entries,
        palette_index_map=palette_index_map,
    )

    variant.palette_entries[0].enabled = False
    rerender_variant_palette(variant, (16,))

    colors_after = {
        variant.master.getpixel((x, y))
        for y in range(2)
        for x in range(2)
        if variant.master.getpixel((x, y))[3] > 0
    }
    assert len(colors_after) <= 1
