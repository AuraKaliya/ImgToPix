from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
STAMP_FILE = VENV_DIR / ".bootstrap-stamp"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def project_hash() -> str:
    return hashlib.sha256(PYPROJECT_FILE.read_bytes()).hexdigest()


def create_venv() -> None:
    if venv_python().exists():
        return

    print("[INFO] Creating virtual environment...")
    if sys.platform == "win32" and shutil.which("py"):
        command = ["py", "-3", "-m", "venv", str(VENV_DIR)]
    else:
        command = [sys.executable, "-m", "venv", str(VENV_DIR)]

    subprocess.run(command, check=True, cwd=REPO_ROOT)


def ensure_installed() -> None:
    expected_hash = project_hash()
    installed_hash = STAMP_FILE.read_text(encoding="utf-8").strip() if STAMP_FILE.exists() else ""
    if installed_hash == expected_hash:
        return

    print("[INFO] Installing or updating project dependencies...")
    subprocess.run(
        [str(venv_python()), "-m", "pip", "install", "-e", "."],
        check=True,
        cwd=REPO_ROOT,
    )
    STAMP_FILE.write_text(expected_hash, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    command = argv if argv else ["gui"]

    create_venv()
    ensure_installed()

    result = subprocess.run(
        [str(venv_python()), "-m", "imagetopixel", *command],
        cwd=REPO_ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
