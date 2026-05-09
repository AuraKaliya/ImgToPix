from pathlib import Path

from PIL import Image

from imagetopixel.core.models import ProcessingOptions
from imagetopixel.core.pixelizer import process_image


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
