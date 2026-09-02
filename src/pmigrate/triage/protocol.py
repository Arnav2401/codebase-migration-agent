"""Phase 4 triage contract (docs/interfaces.md §6, docs/phase-4-triage.md). `FailureClass`
and `Diagnosis` live in `types.py` alongside this project's other shared dataclasses;
`Classifier` lives here, matching how `Sandbox` (sandbox/protocol.py) and `CodemodRule`
(codemod/protocol.py) are each kept in their own module's `protocol.py` rather than in
`types.py` with the plain data shapes.
"""

from __future__ import annotations

from typing import Protocol

from pmigrate.types import BaselineResult, Diagnosis, TestRun


class Classifier(Protocol):
    def classify(self, run: TestRun, baseline: BaselineResult | None) -> list[Diagnosis]:
        """Groups every failing outcome and collection error in `run` into one or more
        `Diagnosis` objects, classified against `FailureClass`. `baseline` is optional —
        a `RepoSpec` without a captured baseline (most ad hoc/test runs) can't have
        `PREEXISTING` classified at all, which is a real, honest limitation, not
        something to fake with a default."""
        ...
