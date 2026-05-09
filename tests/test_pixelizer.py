from pathlib import Path

from PIL import Image

from imagetopixel.core.models import MASTER_SIZE, ProcessingOptions
from imagetopixel.core.pixelizer import process_image
from imagetopixel.core.preprocess import list_algorithms


def test_process_image_outputs_expected_sizes(tmp_path: Path) -> None:
    image = Image.new("RGBA", (80, 60), (128, 200, 90, 255))
    source = tmp_path / "source.png"
    image.save(source)

    result = process_image(source, ProcessingOptions())

    assert result.squared.size == (80, 80)
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

    result = process_image(source, ProcessingOptions(algorithm="median"), include_all_algorithms=True)

    assert result.selected_algorithm == "median"
    assert set(result.variants.keys()) == set(list_algorithms())
    assert result.variants["median"].master.size == (MASTER_SIZE, MASTER_SIZE)
    assert result.outputs[16].tobytes() == result.variants["median"].outputs[16].tobytes()
