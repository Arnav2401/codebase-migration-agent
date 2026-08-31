"""Shared by every CodeGraph backend's `ingest()`: read every first-party .py file under
a checked-out repo root into the {relative_path: bytes} shape resolver.resolve_repo()
expects.
"""

from __future__ import annotations

from pathlib import Path

EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}


def read_py_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        files[str(path.relative_to(root).as_posix())] = path.read_bytes()
    return files
