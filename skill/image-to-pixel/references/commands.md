# Commands

## Primary entrypoints

- `python bootstrap.py gui`
- `python bootstrap.py convert input.png --output output`
- `python bootstrap.py batch ./images --output ./output --recursive`
- `python bootstrap.py doctor`
- `python bootstrap.py docs`

## Maintenance checklist

1. Keep `src/imagetopixel/core/` free of GUI-only logic.
2. Keep CLI behavior aligned with GUI defaults where possible.
3. Update `docs/usage.md`, `docs/gui.md`, and `docs/cli.md` after command changes.
4. Run `pytest` after changing conversion or file-discovery behavior.
5. Re-run skill validation after editing `SKILL.md` or `agents/openai.yaml`.
