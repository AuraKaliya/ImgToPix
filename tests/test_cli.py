from pathlib import Path

from imagetopixel.cli import find_image_files


def test_find_image_files_filters_supported_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(b"png")
    (tmp_path / "b.jpg").write_bytes(b"jpg")
    (tmp_path / "c.txt").write_text("ignore", encoding="utf-8")

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "d.webp").write_bytes(b"webp")

    top_level = find_image_files(tmp_path, recursive=False)
    recursive = find_image_files(tmp_path, recursive=True)

    assert [path.name for path in top_level] == ["a.png", "b.jpg"]
    assert [path.name for path in recursive] == ["a.png", "b.jpg", "d.webp"]
