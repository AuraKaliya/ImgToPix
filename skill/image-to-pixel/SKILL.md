---
name: image-to-pixel
description: Convert high-resolution pseudo-pixel images into true low-resolution pixel-art outputs and operate the ImageToPixel project through its GUI, CLI, bootstrap flow, docs, and export conventions. Use when Codex needs to launch the app, batch-convert images, troubleshoot startup dependencies, or maintain command and usage documentation for this repository.
---

# Image To Pixel

Use this skill to work inside the `ImageToPixel` project as a reusable tool rather than a one-off script.

## Quick Start

Prefer the bootstrap entry for local runs because it creates `.venv`, installs dependencies, and dispatches to the package entrypoint:

```bash
python bootstrap.py gui
python bootstrap.py doctor
python bootstrap.py convert input.png --output output
```

If the environment is already prepared, use the package entrypoint directly:

```bash
python -m imagetopixel gui
python -m imagetopixel batch ./images --output ./output --recursive
```

## Workflow

1. Keep the reusable image-processing logic in `src/imagetopixel/core/`.
2. Treat `src/imagetopixel/gui/` as the desktop interaction layer.
3. Treat `src/imagetopixel/cli.py` as the command surface for automation and future integrations.
4. Update `docs/usage.md`, `docs/gui.md`, and `docs/cli.md` whenever commands or UX change.
5. Use `start.bat` for Windows GUI launch and `bootstrap.py` for scripted invocation.

## Conventions

- Default outputs are `16x16`, `32x32`, and `64x64`.
- Prefer edge padding unless a task explicitly benefits from `mirror` or `solid`.
- Save exported images as `source_stem_size.png`.
- Keep GUI and CLI behavior aligned by routing both through shared core functions.
- When adding new commands, document them in both `--help` text and `docs/cli.md`.

## References

- Read `references/commands.md` for the supported command patterns and maintenance checklist.
