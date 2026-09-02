"""The single write chokepoint (CLAUDE.md, docs/interfaces.md §5, docs/phase-3-loop.md
"Anti-cheating"). Every invariant that matters for this project's credibility is enforced
HERE, mechanically, not in a prompt:

  I1 — the agent never edits test files
  I2 — the agent never skips/deletes tests
  I3 — the agent never pins pydantic <2

docs/decisions.md D10: "All the invariants are enforced in the single function that
applies patches, not in the prompt. That's also why prompt injection through repo comments
can't do much — it can influence what the model *wants* to do, but not what the tool layer
permits." This module is that function.

Design: check BEFORE touching disk (parse_unified_diff is pure), and even after a
successful `git apply`, verify every touched .py file still parses — docs/interfaces.md
§5 says apply_patch validates "applies cleanly, file parses, I1-I3" as one unit, not as
separate steps a caller could accidentally skip.

I1/I2 are deliberately redundant with each other rather than relying on I1 alone: I1 blocks
any diff touching a test-file PATH; I2 additionally scans every file's added lines for
skip/xfail markers and every file's removed lines for deleted test functions, regardless of
path. A model that can't edit tests/test_x.py directly might still try to neuter a test via
a conftest.py fixture or a shared helper — I2 catches that path-independent case too.
"""

from __future__ import annotations

import ast
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pmigrate.agent.diff import FileDiff, parse_unified_diff

Invariant = Literal["I1", "I2", "I3"]

TEST_PATH_PATTERNS = (
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"(^|/)[^/]+_test\.py$"),
    re.compile(r"(^|/)conftest\.py$"),
)

_SKIP_MARKERS = (
    re.compile(r"@pytest\.mark\.skip"),
    re.compile(r"@pytest\.mark\.xfail"),
    re.compile(r"pytest\.skip\("),
    re.compile(r"@unittest\.skip"),
    re.compile(r"@unittest\.expectedFailure"),
)

_TEST_DEF_PATTERN = re.compile(r"^\s*def (test_\w+)")

DEPENDENCY_FILE_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
}

# A constraint that caps pydantic BELOW 2 ("<2", however it's combined with a lower
# bound) permanently excludes v2 — that's the actual invariant, not "does it say
# literally 1". Also catches an exact or compatible-release pin directly on 1.x, which
# has the same effect even without an explicit "<2" anywhere in the string.
_PYDANTIC_UPPER_BOUND_BELOW_2 = re.compile(r"<\s*2\b")
_PYDANTIC_EXACT_OR_COMPAT_V1 = re.compile(r"(?:==|~=)\s*1\.")


def _line_pins_pydantic_v1(line: str) -> bool:
    if "pydantic" not in line:
        return False
    return bool(
        _PYDANTIC_UPPER_BOUND_BELOW_2.search(line) or _PYDANTIC_EXACT_OR_COMPAT_V1.search(line)
    )


def is_test_path(path: str) -> bool:
    return any(p.search(path) for p in TEST_PATH_PATTERNS)


@dataclass(frozen=True)
class PatchViolation:
    invariant: Invariant
    message: str
    file: str | None = None


@dataclass(frozen=True)
class PatchResult:
    applied: bool
    violations: tuple[PatchViolation, ...]
    files_changed: tuple[str, ...]
    stderr: str | None = None


def _check_i1_no_test_file_edits(files: list[FileDiff]) -> list[PatchViolation]:
    return [
        PatchViolation("I1", f"diff touches a test file: {f.path}", file=f.path)
        for f in files
        if is_test_path(f.path)
    ]


def _check_i2_no_skip_or_delete(files: list[FileDiff]) -> list[PatchViolation]:
    violations: list[PatchViolation] = []
    for f in files:
        for line in f.added_lines:
            if any(marker.search(line) for marker in _SKIP_MARKERS):
                violations.append(
                    PatchViolation("I2", f"adds a skip/xfail marker: {line.strip()!r}", file=f.path)
                )

        removed_test_names = {
            m.group(1) for line in f.removed_lines if (m := _TEST_DEF_PATTERN.match(line))
        }
        added_test_names = {
            m.group(1) for line in f.added_lines if (m := _TEST_DEF_PATTERN.match(line))
        }
        for name in removed_test_names - added_test_names:
            violations.append(PatchViolation("I2", f"deletes test function {name!r}", file=f.path))
    return violations


def _check_i3_no_pydantic_v1_pin(files: list[FileDiff]) -> list[PatchViolation]:
    violations: list[PatchViolation] = []
    for f in files:
        if Path(f.path).name not in DEPENDENCY_FILE_NAMES:
            continue
        for line in f.added_lines:
            if _line_pins_pydantic_v1(line):
                violations.append(
                    PatchViolation("I3", f"pins pydantic to v1: {line.strip()!r}", file=f.path)
                )
    return violations


def check_invariants(files: list[FileDiff]) -> list[PatchViolation]:
    return [
        *_check_i1_no_test_file_edits(files),
        *_check_i2_no_skip_or_delete(files),
        *_check_i3_no_pydantic_v1_pin(files),
    ]


def apply_patch(repo_root: Path, unified_diff: str) -> PatchResult:
    files = parse_unified_diff(unified_diff)
    violations = check_invariants(files)
    if violations:
        return PatchResult(applied=False, violations=tuple(violations), files_changed=())

    if not files:
        return PatchResult(applied=True, violations=(), files_changed=())

    # Snapshot in memory before touching disk, rather than reverting via `git checkout`
    # afterward: the working directory here is Phase 2's overlay staging area, a PLAIN
    # directory, not necessarily a git repo — `git checkout` would fail (or silently no-op)
    # outside one. Found by writing the revert test against a non-git tmp_path and watching
    # it fail to actually restore anything.
    original_contents: dict[str, str | None] = {}
    for f in files:
        full_path = repo_root / f.path
        original_contents[f.path] = full_path.read_text() if full_path.exists() else None

    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as fh:
        fh.write(unified_diff)
        patch_path = fh.name

    try:
        check = subprocess.run(
            ["git", "apply", "--check", patch_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if check.returncode != 0:
            return PatchResult(applied=False, violations=(), files_changed=(), stderr=check.stderr)

        result = subprocess.run(
            ["git", "apply", patch_path], cwd=repo_root, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return PatchResult(applied=False, violations=(), files_changed=(), stderr=result.stderr)
    finally:
        Path(patch_path).unlink(missing_ok=True)

    touched_py_files = [f.path for f in files if f.path.endswith(".py") and not f.is_deleted_file]
    for rel_path in touched_py_files:
        full_path = repo_root / rel_path
        try:
            ast.parse(full_path.read_text())
        except SyntaxError as e:
            _revert(repo_root, original_contents)
            return PatchResult(
                applied=False,
                violations=(),
                files_changed=(),
                stderr=f"patch applied but left invalid syntax in {rel_path}: {e}",
            )

    return PatchResult(applied=True, violations=(), files_changed=tuple(f.path for f in files))


def _revert(repo_root: Path, original_contents: dict[str, str | None]) -> None:
    """Restore every touched file to its pre-patch content from the in-memory snapshot —
    `None` means the file didn't exist before (the patch created it), so revert = delete."""
    for rel_path, content in original_contents.items():
        full_path = repo_root / rel_path
        if content is None:
            full_path.unlink(missing_ok=True)
        else:
            full_path.write_text(content)
