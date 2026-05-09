from __future__ import annotations

import argparse
import importlib
import os
import platform
import sys
from pathlib import Path
from typing import Iterable

from imagetopixel.bootstrap import docs_dir, repo_root
from imagetopixel.core.exporter import save_outputs
from imagetopixel.core.image_loader import SUPPORTED_EXTENSIONS, is_supported_image
from imagetopixel.core.models import ProcessingOptions, TARGET_SIZES
from imagetopixel.core.pixelizer import process_image
from imagetopixel.core.preprocess import list_presets
from imagetopixel.gui.main_window import run as run_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagetopixel",
        description="将伪像素图片转换为 16x16、32x32、64x64 的真像素图。",
    )
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="启动图形界面")
    gui_parser.set_defaults(handler=handle_gui)

    convert_parser = subparsers.add_parser("convert", help="转换单张图片")
    convert_parser.add_argument("input", help="输入图片路径")
    convert_parser.add_argument("--output", required=True, help="输出目录")
    add_processing_arguments(convert_parser)
    convert_parser.set_defaults(handler=handle_convert)

    batch_parser = subparsers.add_parser("batch", help="批量转换目录中的图片")
    batch_parser.add_argument("input_dir", help="输入目录")
    batch_parser.add_argument("--output", required=True, help="输出目录")
    batch_parser.add_argument("--recursive", action="store_true", help="递归处理子目录")
    add_processing_arguments(batch_parser)
    batch_parser.set_defaults(handler=handle_batch)

    doctor_parser = subparsers.add_parser("doctor", help="检查运行环境")
    doctor_parser.set_defaults(handler=handle_doctor)

    docs_parser = subparsers.add_parser("docs", help="查看项目文档")
    docs_parser.add_argument(
        "name",
        nargs="?",
        choices=("usage", "gui", "cli"),
        help="指定文档名称",
    )
    docs_parser.add_argument("--open", action="store_true", help="在系统中打开文档")
    docs_parser.set_defaults(handler=handle_docs)

    return parser


def add_processing_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=list(TARGET_SIZES),
        help="输出尺寸，默认 16 32 64",
    )
    parser.add_argument(
        "--padding-mode",
        choices=("edge", "mirror", "solid"),
        default="edge",
        help="补边模式",
    )
    parser.add_argument(
        "--preset",
        choices=list_presets(),
        default="standard",
        help="处理预设",
    )
    parser.add_argument(
        "--save-previews",
        action="store_true",
        help="同时导出放大预览图",
    )


def current_options(args: argparse.Namespace) -> ProcessingOptions:
    sizes = tuple(sorted(set(args.sizes)))
    return ProcessingOptions(
        padding_mode=args.padding_mode,
        preset=args.preset,
        sizes=sizes,
    )


def find_image_files(input_dir: Path, recursive: bool = False) -> list[Path]:
    if recursive:
        candidates: Iterable[Path] = input_dir.rglob("*")
    else:
        candidates = input_dir.iterdir()
    return sorted(path for path in candidates if path.is_file() and is_supported_image(path))


def handle_gui(_: argparse.Namespace) -> int:
    run_gui()
    return 0


def handle_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1

    result = process_image(input_path, current_options(args))
    saved = save_outputs(
        result,
        output_dir=Path(args.output).resolve(),
        options=current_options(args),
        save_previews=args.save_previews,
    )

    print(f"[OK] Converted: {input_path.name}")
    for path in saved:
        print(path)
    return 0


def handle_batch(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        print(f"[ERROR] Input directory not found: {input_dir}")
        return 1

    images = find_image_files(input_dir, recursive=args.recursive)
    if not images:
        print(f"[WARN] No supported images found in: {input_dir}")
        return 0

    options = current_options(args)
    output_dir = Path(args.output).resolve()
    converted = 0

    for image_path in images:
        result = process_image(image_path, options)
        save_outputs(
            result,
            output_dir=output_dir,
            options=options,
            save_previews=args.save_previews,
        )
        converted += 1
        print(f"[OK] Converted: {image_path.name}")

    print(f"[DONE] Converted {converted} image(s) to {output_dir}")
    return 0


def handle_doctor(_: argparse.Namespace) -> int:
    print(f"Python: {platform.python_version()}")
    print(f"Executable: {sys.executable}")
    print(f"Platform: {platform.platform()}")
    print(f"Project root: {repo_root()}")
    print(f"Docs dir: {docs_dir()}")
    print(f"Virtual env: {'yes' if sys.prefix != sys.base_prefix else 'no'}")
    print(f"Supported extensions: {', '.join(SUPPORTED_EXTENSIONS)}")

    for module_name in ("PIL", "numpy", "PySide6"):
        try:
            importlib.import_module(module_name)
            print(f"[OK] {module_name}")
        except Exception as exc:
            print(f"[ERROR] {module_name}: {exc}")
            return 1

    return 0


def handle_docs(args: argparse.Namespace) -> int:
    mapping = {
        "usage": docs_dir() / "usage.md",
        "gui": docs_dir() / "gui.md",
        "cli": docs_dir() / "cli.md",
    }

    if args.name:
        target = mapping[args.name]
        print(target)
        if args.open and os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]
        return 0

    for name, path in mapping.items():
        print(f"{name}: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        args = parser.parse_args(["gui"])

    return args.handler(args)
