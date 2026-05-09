from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from imagetopixel.cli import EXIT_PARTIAL_FAILURE, EXIT_SUCCESS, main


def create_image(path: Path, color: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", (48, 48), color)
    image.save(path)


def test_batch_json_report_and_failure_summary(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "ok.png", (255, 0, 0, 255))
    (input_dir / "broken.png").write_bytes(b"not-an-image")

    report_file = tmp_path / "report.json"
    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(tmp_path / "output"),
            "--json",
            "--report-file",
            str(report_file),
        ]
    )

    assert exit_code == EXIT_PARTIAL_FAILURE

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)
    assert payload["summary"]["succeeded"] == 1
    assert payload["summary"]["failed"] == 1
    assert any(item["status"] == "failed" for item in payload["items"])

    report_payload = json.loads(report_file.read_text(encoding="utf-8"))
    assert report_payload["summary"] == payload["summary"]


def test_batch_stdout_compact_omits_saved_files(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "ok.png", (255, 0, 0, 255))

    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(tmp_path / "output"),
            "--stdout-report",
            "compact",
        ]
    )

    assert exit_code == EXIT_SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["succeeded"] == 1
    assert "saved_files" not in payload["items"][0]
    assert payload["items"][0]["saved_count"] == 3


def test_batch_mirror_name_mode_preserves_relative_structure(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    nested_dir = input_dir / "chars"
    nested_dir.mkdir(parents=True)
    create_image(nested_dir / "hero.png", (0, 255, 0, 255))

    output_dir = tmp_path / "output"
    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(output_dir),
            "--recursive",
            "--name-mode",
            "mirror",
        ]
    )

    assert exit_code == EXIT_SUCCESS
    assert (output_dir / "chars" / "hero_16.png").is_file()


def test_batch_parent_name_mode_uses_parent_prefix(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    nested_dir = input_dir / "icons"
    nested_dir.mkdir(parents=True)
    create_image(nested_dir / "sword.png", (0, 0, 255, 255))

    output_dir = tmp_path / "output"
    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(output_dir),
            "--recursive",
            "--name-mode",
            "parent",
        ]
    )

    assert exit_code == EXIT_SUCCESS
    assert (output_dir / "icons__sword_16.png").is_file()


def test_batch_skip_existing_marks_item_skipped(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "hero.png", (0, 255, 0, 255))

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    sentinel = output_dir / "hero_16.png"
    sentinel.write_bytes(b"sentinel")

    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(output_dir),
            "--skip-existing",
            "--stdout-report",
            "full",
        ]
    )

    assert exit_code == EXIT_SUCCESS
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["skipped"] == 1
    assert payload["items"][0]["status"] == "skipped"
    assert sentinel.read_bytes() == b"sentinel"


def test_batch_summary_file_markdown_is_written(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_image(input_dir / "hero.png", (255, 0, 255, 255))

    summary_file = tmp_path / "summary.md"
    exit_code = main(
        [
            "batch",
            str(input_dir),
            "--output",
            str(tmp_path / "output"),
            "--summary-file",
            str(summary_file),
        ]
    )

    assert exit_code == EXIT_SUCCESS
    content = summary_file.read_text(encoding="utf-8")
    assert "# Batch Summary" in content
    assert "| Status | Input |" in content
