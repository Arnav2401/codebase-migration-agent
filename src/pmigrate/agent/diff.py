"""Pure parsing of a unified diff (the `git diff`/`diff --git` format — verified against a
real `git diff` output before writing this, not the notionally-similar but subtly different
plain `diff -u` format). No filesystem access here; `patch.py`'s invariant checks run
against this parsed shape before anything ever touches disk.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

_FILE_HEADER = re.compile(r"^diff --git a/(?P<a>.+) b/(?P<b>.+)$")
_OLD_PATH = re.compile(r"^--- (?:a/(?P<path>.+)|/dev/null)$")
_NEW_PATH = re.compile(r"^\+\+\+ (?:b/(?P<path>.+)|/dev/null)$")


@dataclass(frozen=True)
class FileDiff:
    path: str
    is_new_file: bool
    is_deleted_file: bool
    added_lines: tuple[str, ...] = field(default_factory=tuple)
    removed_lines: tuple[str, ...] = field(default_factory=tuple)


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    path: str | None = None
    is_new = False
    is_deleted = False
    added: list[str] = []
    removed: list[str] = []

    def _flush() -> None:
        if path is not None:
            files.append(
                FileDiff(
                    path=path,
                    is_new_file=is_new,
                    is_deleted_file=is_deleted,
                    added_lines=tuple(added),
                    removed_lines=tuple(removed),
                )
            )

    for line in diff_text.splitlines():
        header_match = _FILE_HEADER.match(line)
        if header_match:
            _flush()
            path = header_match.group("b")
            is_new = False
            is_deleted = False
            added = []
            removed = []
            continue

        old_match = _OLD_PATH.match(line)
        if old_match:
            if old_match.group("path") is None:
                is_new = True
            continue

        new_match = _NEW_PATH.match(line)
        if new_match:
            if new_match.group("path") is None:
                is_deleted = True
            continue

        if path is None:
            continue  # preamble/garbage before the first file header — ignore

        if line.startswith("@@") or line.startswith("index ") or line.startswith("diff "):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    _flush()
    return files


def make_unified_diff(path: str, before: str, after: str) -> str:
    """The inverse of parse_unified_diff: generates a diff in the same `git diff` shape
    apply_patch expects — verified directly that `git apply` accepts a manually-built
    `diff --git a/X b/X` header in front of difflib's plain unified-diff body, which is
    what this constructs (difflib alone doesn't emit that line, but parse_unified_diff's
    _FILE_HEADER pattern requires it to associate hunks with a path)."""
    if before == after:
        return ""
    hunk_lines = list(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )
    )
    return f"diff --git a/{path} b/{path}\n" + "".join(hunk_lines)
