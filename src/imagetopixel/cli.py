from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Iterable

from imagetopixel.bootstrap import docs_dir, repo_root
from imagetopixel.core.exporter import build_output_paths, save_outputs
from imagetopixel.core.image_loader import SUPPORTED_EXTENSIONS, is_supported_image
from imagetopixel.core.models import ProcessingOptions, TARGET_SIZES
from imagetopixel.core.pixelizer import process_image
from imagetopixel.core.preprocess import list_algorithms, list_contours
from imagetopixel.gui.main_window import run as run_gui


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_PARTIAL_FAILURE = 2


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
    add_overwrite_arguments(convert_parser)
    add_reporting_arguments(convert_parser)
    convert_parser.set_defaults(handler=handle_convert)

    batch_parser = subparsers.add_parser("batch", help="批量转换目录中的图片")
    batch_parser.add_argument("input_dir", help="输入目录")
    batch_parser.add_argument("--output", required=True, help="输出目录")
    batch_parser.add_argument("--recursive", action="store_true", help="递归处理子目录")
    batch_parser.add_argument(
        "--name-mode",
        choices=("flat", "parent", "mirror"),
        default="flat",
        help="批量命名策略：flat=仅文件名，parent=带父目录前缀，mirror=保留原目录结构",
    )
    batch_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="遇到首个失败就停止批处理",
    )
    add_processing_arguments(batch_parser)
    add_overwrite_arguments(batch_parser)
    add_reporting_arguments(batch_parser)
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
        "--algorithm",
        "--preset",
        dest="algorithm",
        choices=list_algorithms(),
        default="majority",
        help="16x16 轮廓内的颜色算法",
    )
    parser.add_argument(
        "--contour",
        choices=list_contours(),
        default="hybrid",
        help="16x16 轮廓方案",
    )
    parser.add_argument(
        "--save-previews",
        action="store_true",
        help="同时导出放大预览图",
    )


def add_overwrite_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的输出文件，默认行为",
    )
    group.add_argument(
        "--skip-existing",
        action="store_true",
        help="若目标输出已存在，则跳过该输入文件",
    )


def add_reporting_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stdout-report",
        choices=("compact", "full"),
        help="将结构化结果报告输出到标准输出",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="兼容旧行为，等同于 --stdout-report full",
    )
    parser.add_argument(
        "--report-file",
        help="将完整结果报告保存为 JSON 文件",
    )
    parser.add_argument(
        "--summary-file",
        help="将批处理摘要保存为 .csv 或 .md 文件",
    )


def current_options(args: argparse.Namespace) -> ProcessingOptions:
    sizes = tuple(sorted(set(args.sizes)))
    return ProcessingOptions(
        padding_mode=args.padding_mode,
        algorithm=args.algorithm,
        contour=args.contour,
        sizes=sizes,
    )


def find_image_files(input_dir: Path, recursive: bool = False) -> list[Path]:
    if recursive:
        candidates: Iterable[Path] = input_dir.rglob("*")
    else:
        candidates = input_dir.iterdir()
    return sorted(path for path in candidates if path.is_file() and is_supported_image(path))


def build_base_name(image_path: Path, mode: str) -> str:
    if mode == "parent":
        parent_name = image_path.parent.name
        if parent_name:
            return f"{parent_name}__{image_path.stem}"
    return image_path.stem


def build_output_subdir(image_path: Path, input_root: Path, mode: str) -> Path | None:
    if mode != "mirror":
        return None

    relative_parent = image_path.parent.relative_to(input_root)
    if str(relative_parent) == ".":
        return None
    return relative_parent


def report_mode(args: argparse.Namespace) -> str | None:
    if args.json:
        return "full"
    return args.stdout_report


def should_emit_machine_stdout(args: argparse.Namespace) -> bool:
    return report_mode(args) is not None


def make_report_payload(
    *,
    command: str,
    ok: bool,
    summary: dict,
    items: list[dict],
) -> dict:
    return {
        "command": command,
        "ok": ok,
        "summary": summary,
        "items": items,
    }


def make_compact_payload(payload: dict) -> dict:
    compact_items = []
    for item in payload["items"]:
        compact_items.append(
            {
                "input": item.get("input", ""),
                "relative_input": item.get("relative_input", ""),
                "status": item.get("status", ""),
                "saved_count": len(item.get("saved_files", [])),
                "error": item.get("error", ""),
            }
        )

    return {
        "command": payload["command"],
        "ok": payload["ok"],
        "summary": payload["summary"],
        "items": compact_items,
    }


def emit_report(args: argparse.Namespace, payload: dict) -> None:
    if args.report_file:
        report_path = Path(args.report_file).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    mode = report_mode(args)
    if mode == "full":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif mode == "compact":
        print(json.dumps(make_compact_payload(payload), ensure_ascii=False, indent=2))


def write_summary_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "status",
                    "input",
                    "relative_input",
                    "base_name",
                    "output_subdir",
                    "saved_count",
                    "error",
                ]
            )
            for item in payload["items"]:
                writer.writerow(
                    [
                        item.get("status", ""),
                        item.get("input", ""),
                        item.get("relative_input", ""),
                        item.get("base_name", ""),
                        item.get("output_subdir", ""),
                        len(item.get("saved_files", [])),
                        item.get("error", ""),
                    ]
                )
        return

    if suffix in {".md", ".markdown"}:
        lines = [
            "# Batch Summary",
            "",
            "| Status | Input | Relative Input | Base Name | Output Subdir | Saved Count | Error |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
        for item in payload["items"]:
            lines.append(
                "| {status} | {input} | {relative_input} | {base_name} | {output_subdir} | {saved_count} | {error} |".format(
                    status=item.get("status", ""),
                    input=item.get("input", ""),
                    relative_input=item.get("relative_input", ""),
                    base_name=item.get("base_name", ""),
                    output_subdir=item.get("output_subdir", ""),
                    saved_count=len(item.get("saved_files", [])),
                    error=item.get("error", "").replace("|", "\\|"),
                )
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    raise ValueError("summary-file only supports .csv, .md, or .markdown")


def apply_summary_file(args: argparse.Namespace, payload: dict) -> None:
    if args.summary_file:
        write_summary_file(Path(args.summary_file).resolve(), payload)


def human_print(args: argparse.Namespace, message: str) -> None:
    if not should_emit_machine_stdout(args):
        print(message)


def maybe_skip_existing(expected_paths: list[Path], args: argparse.Namespace) -> bool:
    return bool(args.skip_existing and any(path.exists() for path in expected_paths))


def build_item_base(
    image_path: Path,
    *,
    relative_input: Path | None = None,
    base_name: str = "",
    output_subdir: str = "",
) -> dict:
    item = {
        "input": str(image_path),
        "status": "",
        "ok": False,
        "saved_files": [],
        "base_name": base_name,
        "output_subdir": output_subdir,
    }
    if relative_input is not None:
        item["relative_input"] = str(relative_input)
    return item


def build_summary(
    *,
    total: int,
    succeeded: int,
    failed: int,
    skipped: int,
    **extra: object,
) -> dict:
    summary = {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
    summary.update(extra)
    return summary


def handle_gui(_: argparse.Namespace) -> int:
    run_gui()
    return EXIT_SUCCESS


def handle_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    options = current_options(args)

    if not input_path.is_file():
        item = build_item_base(input_path)
        item.update(status="failed", error=f"Input file not found: {input_path}")
        payload = make_report_payload(
            command="convert",
            ok=False,
            summary=build_summary(total=1, succeeded=0, failed=1, skipped=0),
            items=[item],
        )
        emit_report(args, payload)
        apply_summary_file(args, payload)
        human_print(args, f"[ERROR] Input file not found: {input_path}")
        return EXIT_FAILURE

    try:
        result = process_image(input_path, options)
        expected_paths = build_output_paths(
            result,
            output_dir=output_dir,
            options=options,
            save_previews=args.save_previews,
        )
        if maybe_skip_existing(expected_paths, args):
            item = build_item_base(input_path)
            item.update(
                status="skipped",
                ok=True,
                saved_files=[str(path.resolve()) for path in expected_paths],
                reason="existing_outputs",
            )
            payload = make_report_payload(
                command="convert",
                ok=True,
                summary=build_summary(total=1, succeeded=0, failed=0, skipped=1),
                items=[item],
            )
            emit_report(args, payload)
            apply_summary_file(args, payload)
            human_print(args, f"[SKIP] Existing outputs for: {input_path.name}")
            return EXIT_SUCCESS

        saved = save_outputs(
            result,
            output_dir=output_dir,
            options=options,
            save_previews=args.save_previews,
        )
        item = build_item_base(input_path)
        item.update(
            status="succeeded",
            ok=True,
            padding=list(result.padding),
            saved_files=[str(path.resolve()) for path in saved],
            algorithm=result.selected_algorithm,
            contour=result.selected_contour,
            sizes=list(options.sizes),
        )
        payload = make_report_payload(
            command="convert",
            ok=True,
            summary=build_summary(total=1, succeeded=1, failed=0, skipped=0),
            items=[item],
        )
        emit_report(args, payload)
        apply_summary_file(args, payload)
        human_print(args, f"[OK] Converted: {input_path.name}")
        if not should_emit_machine_stdout(args):
            for path in saved:
                print(path)
        return EXIT_SUCCESS
    except Exception as exc:
        item = build_item_base(input_path)
        item.update(status="failed", error=str(exc))
        payload = make_report_payload(
            command="convert",
            ok=False,
            summary=build_summary(total=1, succeeded=0, failed=1, skipped=0),
            items=[item],
        )
        emit_report(args, payload)
        apply_summary_file(args, payload)
        human_print(args, f"[ERROR] Failed to convert {input_path.name}: {exc}")
        return EXIT_FAILURE


def handle_batch(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output).resolve()
    options = current_options(args)

    if not input_dir.is_dir():
        item = build_item_base(input_dir)
        item.update(status="failed", error=f"Input directory not found: {input_dir}")
        payload = make_report_payload(
            command="batch",
            ok=False,
            summary=build_summary(total=0, succeeded=0, failed=1, skipped=0),
            items=[item],
        )
        emit_report(args, payload)
        apply_summary_file(args, payload)
        human_print(args, f"[ERROR] Input directory not found: {input_dir}")
        return EXIT_FAILURE

    images = find_image_files(input_dir, recursive=args.recursive)
    if not images:
        payload = make_report_payload(
            command="batch",
            ok=True,
            summary=build_summary(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                stopped_early=False,
                name_mode=args.name_mode,
                existing_mode="skip" if args.skip_existing else "overwrite",
            ),
            items=[],
        )
        emit_report(args, payload)
        apply_summary_file(args, payload)
        human_print(args, f"[WARN] No supported images found in: {input_dir}")
        return EXIT_SUCCESS

    items: list[dict] = []
    converted = 0
    failed = 0
    skipped = 0

    for image_path in images:
        base_name = build_base_name(image_path, args.name_mode)
        output_subdir = build_output_subdir(image_path, input_dir, args.name_mode)
        relative_input = image_path.relative_to(input_dir)
        output_subdir_text = str(output_subdir) if output_subdir else ""
        item = build_item_base(
            image_path,
            relative_input=relative_input,
            base_name=base_name,
            output_subdir=output_subdir_text,
        )

        try:
            result = process_image(image_path, options)
            expected_paths = build_output_paths(
                result,
                output_dir=output_dir,
                options=options,
                save_previews=args.save_previews,
                base_name=base_name,
                output_subdir=output_subdir,
            )
            if maybe_skip_existing(expected_paths, args):
                item.update(
                    status="skipped",
                    ok=True,
                    saved_files=[str(path.resolve()) for path in expected_paths],
                    reason="existing_outputs",
                )
                items.append(item)
                skipped += 1
                human_print(args, f"[SKIP] Existing outputs for: {relative_input}")
                continue

            saved = save_outputs(
                result,
                output_dir=output_dir,
                options=options,
                save_previews=args.save_previews,
                base_name=base_name,
                output_subdir=output_subdir,
            )
            item.update(
                status="succeeded",
                ok=True,
                padding=list(result.padding),
                saved_files=[str(path.resolve()) for path in saved],
                algorithm=result.selected_algorithm,
                contour=result.selected_contour,
            )
            items.append(item)
            converted += 1
            human_print(args, f"[OK] Converted: {relative_input}")
        except Exception as exc:
            item.update(status="failed", error=str(exc))
            items.append(item)
            failed += 1
            human_print(args, f"[ERROR] Failed: {relative_input} -> {exc}")
            if args.stop_on_error:
                break

    payload = make_report_payload(
        command="batch",
        ok=failed == 0,
        summary=build_summary(
            total=len(items),
            succeeded=converted,
            failed=failed,
            skipped=skipped,
            stopped_early=bool(args.stop_on_error and failed > 0),
            name_mode=args.name_mode,
            existing_mode="skip" if args.skip_existing else "overwrite",
        ),
        items=items,
    )
    emit_report(args, payload)
    apply_summary_file(args, payload)
    human_print(
        args,
        f"[DONE] Converted {converted} image(s), skipped {skipped}, failed {failed}, output: {output_dir}",
    )

    if failed == 0:
        return EXIT_SUCCESS
    if converted > 0 or skipped > 0:
        return EXIT_PARTIAL_FAILURE
    return EXIT_FAILURE


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
            return EXIT_FAILURE

    return EXIT_SUCCESS


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
        return EXIT_SUCCESS

    for name, path in mapping.items():
        print(f"{name}: {path}")
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        args = parser.parse_args(["gui"])

    return args.handler(args)
