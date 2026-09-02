"""The Sandbox contract from docs/interfaces.md §3, mirroring how graph/protocol.py fixes
the CodeGraph contract once for every backend.

One small, deliberate widening from the doc: `workdir_overlay` is `Path | None` rather than
`Path`. A run with zero edits yet — the very first full-suite baseline check before the
agent has touched anything — has nothing to overlay, and forcing a call site to invent an
empty directory just to satisfy the type is exactly the kind of validation-for-a-scenario-
that-can't-happen this project's own conventions argue against.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pmigrate.types import ImageRef, RepoSpec, SandboxPolicy, TestRun


class Sandbox(Protocol):
    def build(self, repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> ImageRef:
        """Cached by (repo_id, sha, deps-hash, pydantic). Network allowed here only."""
        ...

    def run_tests(
        self,
        image: ImageRef,
        workdir_overlay: Path | None,
        policy: SandboxPolicy,
        selection: list[str] | None = None,
    ) -> TestRun:
        """Network is OFF. selection lets triage re-run just the failures."""
        ...
