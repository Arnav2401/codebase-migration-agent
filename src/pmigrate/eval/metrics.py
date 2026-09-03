"""The only place scoring happens (CLAUDE.md: never compute a metric in more than one
place). Every function here is pure — given a `RepoSpec` and the graph's final state,
returns a number. No I/O, no printing, no Docker.

docs/decisions.md D40/D57: `RepoResult` (renamed from Phase 4's `RepoScore`) is now
Phase 5's full sketch from interfaces.md §8, carrying an `EvalConfig` instead of a bare
`use_triage: bool` — `diff_line_jaccard`/`symbol_precision`/`symbol_recall`/`trace_path`
exist as `| None` fields (that later Phase 5 components will populate) rather than being
absent, since a missing field would be a breaking change to add later where `None` isn't.
Per-class fix-success counts, once on this "not in this pass" list, are no longer absent:
D51 gave `AgentState` the repair-attempt history this needed, and
`ScoredRepairAttempt`/`fix_success_table` below are the join.

docs/decisions.md D46: reads `final_state["cumulative_outcomes"]`, NOT
`final_state["last_run"].outcomes` — `last_run` is only the most recent (often
`selection`-narrowed, covering just previously-failing node_ids) test run, so relying on
it alone silently drops every already-passing test that wasn't re-tested since the first
iteration. Found live on a real corpus run: a repo's true state was 173/195 passing, but
its FINAL iteration's `last_run` only covered a 22-test narrow re-run, which would have
scored as ~1/195 if this hadn't been fixed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pmigrate.agent.state import RepairAttempt
from pmigrate.eval.config import EvalConfig
from pmigrate.triage.collect import collect_raw_failures
from pmigrate.triage.grouping import group_raw_failures
from pmigrate.triage.label import LabelledFailure
from pmigrate.types import FailureClass, RepoSpec, TestOutcome


def classifier_accuracy(labelled: Sequence[LabelledFailure]) -> float:
    """docs/phase-4-triage.md acceptance criterion: >=85% on >=100 hand-labelled real
    failures. Pure comparison of `predicted_cls` vs `true_cls` -- the human judgment that
    produces `true_cls` lives entirely in `triage/label.py`'s interactive tool (which
    deliberately never sees `predicted_cls` while asking), so this function can't be the
    thing that accidentally makes the check circular. 0.0 on an empty input rather than
    raising or reporting 100% -- "no labelled data" and "perfect accuracy" must never
    look the same."""
    if not labelled:
        return 0.0
    correct = sum(1 for lf in labelled if lf.predicted_cls == lf.true_cls)
    return correct / len(labelled)


@dataclass(frozen=True)
class ScoredRepairAttempt:
    """One `RepairAttempt` (agent/state.py) paired with whether it actually worked --
    docs/decisions.md D51 deliberately left this join out of `repair()` itself, since it
    needs the run's FINAL `cumulative_outcomes` to answer, not anything knowable mid-loop.

    `fixed` is True only when `attempt.outcome == "applied"` AND every one of
    `attempt.node_ids` shows `status == "passed"` in the final `cumulative_outcomes` --
    every other outcome is unconditionally False, even if the SAME node_ids ended up
    passing later: no code changed in this attempt, so crediting it with a fix a
    DIFFERENT, later attempt actually made would be dishonest. Known limitation, not
    hidden: only end-state outcomes are retained, not a per-iteration snapshot, so this
    can't distinguish "this attempt caused the fix" from "this attempt's targets happened
    to already be passing again by the time a later attempt or run confirmed it" --
    the same ambiguity docs/results/triage.md already flags by hand for rohmu's
    "inconclusive" second attempt, now computed the same way for every attempt instead.
    """

    attempt: RepairAttempt
    fixed: bool


def _score_repair_attempt(
    attempt: RepairAttempt, cumulative_outcomes: dict[str, TestOutcome]
) -> ScoredRepairAttempt:
    fixed = (
        attempt.outcome == "applied"
        and bool(attempt.node_ids)
        and all(
            cumulative_outcomes.get(nid) is not None and cumulative_outcomes[nid].status == "passed"
            for nid in attempt.node_ids
        )
    )
    return ScoredRepairAttempt(attempt=attempt, fixed=fixed)


@dataclass(frozen=True)
class ClassFixSuccess:
    """One row of docs/phase-4-triage.md's per-class fix-success table -- aggregated
    ACROSS repos by `fix_success_table` below, not per-repo (a single repo rarely has
    enough attempts of one class for a rate to mean anything)."""

    cls: FailureClass | None  # None groups every config.triage=False attempt (no single class)
    attempts: int
    applied: int  # attempts where an edit actually landed, whether or not it fixed anything
    fixed: int

    @property
    def fix_rate(self) -> float:
        return self.fixed / self.applied if self.applied else 0.0


def fix_success_table(results: Sequence[RepoResult]) -> dict[FailureClass | None, ClassFixSuccess]:
    """The actual artefact docs/phase-4-triage.md calls "the single most valuable
    artefact in the project for interviews" -- one row per FailureClass, counting every
    scored repair attempt across the whole corpus run (both `config.triage` arms mixed
    together unless the caller filters `results` first)."""
    counts: dict[FailureClass | None, tuple[int, int, int]] = {}
    for result in results:
        for scored in result.scored_repairs:
            key = scored.attempt.cls
            attempts, applied, fixed = counts.get(key, (0, 0, 0))
            attempts += 1
            applied += int(scored.attempt.outcome == "applied")
            fixed += int(scored.fixed)
            counts[key] = (attempts, applied, fixed)
    return {
        cls: ClassFixSuccess(cls=cls, attempts=a, applied=p, fixed=f)
        for cls, (a, p, f) in counts.items()
    }


@dataclass(frozen=True)
class RepoResult:
    """Phase 5's full result type (interfaces.md §8), superseding Phase 4's `RepoScore`
    (docs/decisions.md D40/D57) — one type, not two, per CLAUDE.md's "never compute a
    metric in more than one place" rule. Keeps `RepoScore`'s established field names
    (`usd_spent`, `final_diagnosis_counts`) rather than interfaces.md's original
    `usd`/`failure_classes` sketch — renaming now would be pure churn across every call
    site for zero functional benefit, since the sketch predates the real implementation."""

    repo_id: str
    config: EvalConfig  # which ablation arm produced this result (docs/decisions.md D40/D57)
    pass_rate: float  # |baseline.passed ∩ still-passing| / |baseline.passed| (I4)
    full_green: bool  # pass_rate >= 1.0
    iterations: int
    usd_spent: float
    wallclock_s: float
    final_diagnosis_counts: Counter[FailureClass]  # from the LAST classify_node call only
    # docs/phase-4-triage.md acceptance criterion: "avg failures-per-diagnosis > 1" as
    # evidence grouping is consolidating related failures, not routing one-by-one. Same
    # "last classify call only" scope as final_diagnosis_counts above — recomputed here via
    # group_raw_failures rather than read off `diagnoses` because classify_and_group's own
    # return type (list[Diagnosis], the Classifier protocol's contract) already discards
    # each group's raw-failure count. 0.0 when there's nothing left to group (full_green or
    # no last_run yet) — distinct from 1.0, which means every failure got its own diagnosis.
    avg_failures_per_diagnosis: float
    scored_repairs: tuple[ScoredRepairAttempt, ...]
    # docs/decisions.md D57: None, not 0.0, until the diff-similarity component (a later
    # Phase 5 step) actually computes these — a real 0.0 (e.g. zero symbol overlap) must
    # stay distinguishable from "not measured yet," the same reasoning classifier_accuracy
    # above already applies to "no labelled data" vs "100% accuracy."
    diff_line_jaccard: float | None = None
    symbol_precision: float | None = None
    symbol_recall: float | None = None
    trace_path: str | None = None  # Phase 6 concept; stays None until that phase unlocks


def score_run(
    repo: RepoSpec, final_state: Any, wallclock_s: float, *, config: EvalConfig
) -> RepoResult:
    """`final_state` is whatever `build_migration_graph(...).invoke(...)` returns —
    typed `Any` here for the same reason `agent/graph.py` types the compiled graph
    itself `Any`: LangGraph's runtime return shape (a dict keyed by `AgentState`'s
    field names, confirmed by every existing `test_graph.py` test's `result["status"]`
    style access) isn't a type this project's code declares or controls."""
    if repo.baseline is None:
        raise ValueError(f"{repo.repo_id} has no captured baseline to score against (I4)")

    cumulative_outcomes = final_state.get("cumulative_outcomes", {})
    passing_now = frozenset(
        node_id for node_id, o in cumulative_outcomes.items() if o.status == "passed"
    )
    still_passing = repo.baseline.passed & passing_now
    pass_rate = len(still_passing) / len(repo.baseline.passed) if repo.baseline.passed else 1.0

    budget = final_state["budget"]
    diagnoses = final_state.get("diagnoses", [])

    last_run = final_state.get("last_run")
    if last_run is None:
        avg_failures_per_diagnosis = 0.0
    else:
        grouped = group_raw_failures(collect_raw_failures(last_run), repo.baseline)
        avg_failures_per_diagnosis = (
            sum(len(g.raw_failures) for g in grouped) / len(grouped) if grouped else 0.0
        )

    repair_attempts = final_state.get("repair_attempts", [])
    scored_repairs = tuple(_score_repair_attempt(a, cumulative_outcomes) for a in repair_attempts)

    return RepoResult(
        repo_id=repo.repo_id,
        config=config,
        pass_rate=pass_rate,
        full_green=pass_rate >= 1.0,
        iterations=budget.iterations,
        usd_spent=budget.usd_spent,
        wallclock_s=wallclock_s,
        final_diagnosis_counts=Counter(d.cls for d in diagnoses),
        avg_failures_per_diagnosis=avg_failures_per_diagnosis,
        scored_repairs=scored_repairs,
    )
