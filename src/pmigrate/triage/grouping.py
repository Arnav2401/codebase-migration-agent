"""Classifies each raw failure, then groups failures that share a root cause into one
`Diagnosis` each (docs/phase-4-triage.md: "twenty tests failing from one bad import is ONE
problem... group by (class, root traceback frame) before routing, and fix once").

`Diagnosis.suspect_symbols` is always `()` here — interfaces.md §6 sketches it as a
graph-backed lookup ("traceback frames -> graph lookup"), but `CodeGraph` was never wired
into the live agent loop at all (docs/decisions.md D25/D28 made the same call for T2's
`repair.py`: a name-based heuristic covers what's needed so far without it). Wiring a real
graph lookup here is a natural, well-scoped future improvement — it would let `repair()`
consume `suspect_symbols` directly instead of `find_related_files`'s own LibCST base-class
walk — but it's a separate piece of work, not a blocker for classification or grouping to
be correct and useful on their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from pmigrate.traceback_utils import deepest_first_party_frame
from pmigrate.triage.collect import RawFailure
from pmigrate.triage.rules import classify_text
from pmigrate.types import BaselineResult, Diagnosis, FailureClass


@dataclass(frozen=True)
class GroupedDiagnosis:
    """A `Diagnosis` alongside the full `RawFailure`s it was built from.
    `Diagnosis.evidence` is a short (~200 char) snippet for display/grouping — nowhere
    near enough for `agent/repair.py`'s `extract_target_file`, which needs the full
    multi-line traceback to find a `path.py:lineno:` frame. Kept as a SEPARATE type
    rather than added as a field on `Diagnosis` itself, so `Diagnosis` stays exactly the
    shape interfaces.md §6 documents and `Classifier.classify()` keeps returning exactly
    `list[Diagnosis]` — this is `group_raw_failures`'s richer return value, for callers
    (like `agent/graph.py`'s `repair()`) that need to act on a specific diagnosis, not
    just report it."""

    diagnosis: Diagnosis
    raw_failures: tuple[RawFailure, ...]


def _classify_one(
    failure: RawFailure, baseline: BaselineResult | None
) -> tuple[FailureClass, str, str, float]:
    """Returns (cls, strategy, evidence, confidence) for one raw failure. `PREEXISTING`
    is checked FIRST and doesn't need the failure text at all — if a node already failed
    at the pre-migration baseline, WHY it fails now is irrelevant (invariant I4: it was
    never a valid part of the scoring denominator to begin with)."""
    if baseline is not None and failure.node_id is not None and failure.node_id in baseline.failed:
        return FailureClass.PREEXISTING, "ignore", f"failed at baseline: {failure.node_id}", 1.0

    rule = classify_text(failure.text)
    if rule is None:
        return FailureClass.UNKNOWN, "unknown", failure.text[:200], 0.0

    match = rule.pattern.search(failure.text)
    evidence = match.group(0) if match else failure.text[:200]
    return rule.cls, rule.strategy, evidence, rule.confidence


def group_raw_failures(
    raw_failures: tuple[RawFailure, ...], baseline: BaselineResult | None
) -> list[GroupedDiagnosis]:
    GroupKey = tuple[FailureClass, str | None]
    groups: dict[GroupKey, list[RawFailure]] = {}
    # every member of a group shares the same (cls, strategy) by construction — grouped
    # on cls already, and strategy is a pure function of cls in the current rule set —
    # so the FIRST member's (strategy, evidence, confidence) represents the whole group.
    group_meta: dict[GroupKey, tuple[str, str, float]] = {}

    for failure in raw_failures:
        cls, strategy, evidence, confidence = _classify_one(failure, baseline)
        key = (cls, deepest_first_party_frame(failure.text))
        groups.setdefault(key, []).append(failure)
        group_meta.setdefault(key, (strategy, evidence, confidence))

    grouped = []
    for key, members in groups.items():
        cls, _root_frame = key
        strategy, evidence, confidence = group_meta[key]
        diagnosis = Diagnosis(
            node_ids=tuple(m.node_id for m in members if m.node_id is not None),
            cls=cls,
            confidence=confidence,
            evidence=evidence,
            suspect_symbols=(),  # graph-backed symbol lookup deferred — see module docstring
            strategy=strategy,
        )
        grouped.append(GroupedDiagnosis(diagnosis=diagnosis, raw_failures=tuple(members)))
    return grouped


def classify_and_group(
    raw_failures: tuple[RawFailure, ...], baseline: BaselineResult | None
) -> list[Diagnosis]:
    """`Classifier.classify()`'s exact documented return shape (interfaces.md §6) — for
    the richer per-diagnosis raw-failure access `agent/graph.py`'s `repair()` needs, see
    `group_raw_failures` above."""
    return [g.diagnosis for g in group_raw_failures(raw_failures, baseline)]
