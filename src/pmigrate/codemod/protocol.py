"""The CodemodRule contract (docs/interfaces.md §4, docs/phase-3-loop.md T1). Each rule is
a small, independently-testable LibCST transform. `confidence` is not decoration — it flows
through to the PR confidence score (Phase 6) and decides whether a targeted-fix strategy
(Phase 4) re-reviews a rule's own output.

Design note worth being explicit about: rules are pattern-based, not type-inferring. A rule
that rewrites `.dict()` -> `.model_dump()` matches the call SHAPE (an attribute call named
`dict`), not "this object is provably a pydantic model" — that would need whole-program type
inference this project doesn't have. This is the same trade-off pydantic's own official
`bump-pydantic` codemod tool makes, not a shortcut unique to this project. The safety net is
structural, not rule-level precision: docs/phase-3-loop.md's agent loop always re-runs the
test suite after every edit (T1 included) and repairs or reverts on a regression — a rule
firing on a false-positive match is expected to be *caught*, not *prevented*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import libcst as cst

Confidence = Literal["mechanical", "likely", "needs-review"]


@dataclass(frozen=True)
class RuleEdit:
    rule_id: str
    path: str  # filled in by engine.apply_rules, which is the thing that knows the path
    line: int
    before: str
    after: str
    note: str | None = None


class CodemodRule(Protocol):
    id: str
    description: str
    confidence: Confidence

    def applies(self, tree: cst.Module) -> bool:
        """Cheap pre-check so the engine can skip rules that clearly don't match, without
        paying for a full CSTTransformer pass on every rule for every file."""
        ...

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        """Returns the (possibly) transformed tree and the edits made. A needs-review rule
        returns the tree UNCHANGED with a note-only RuleEdit — see phase-3-loop.md:
        "needs-review rules should flag, not rewrite.\""""
        ...
