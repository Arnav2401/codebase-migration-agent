"""The only place scoring happens (CLAUDE.md: never compute a metric in more than one
place). Every function here is pure — given a `RepoSpec` and the graph's final state,
returns a number. No I/O, no printing, no Docker.

docs/decisions.md D40: this is Phase 4's minimal slice, not Phase 5's full
`EvalConfig`/`RepoResult` sketch (interfaces.md §8) — `diff_line_jaccard`,
`symbol_precision`/`recall`, and per-class fix-success counts are deliberately absent.
The first two are Phase 5 ablation-comparison metrics Phase 4's own acceptance criteria
don't need; the third needs `AgentState` to retain repair-attempt/run history it doesn't
have yet (see D40's "deliberately not in this pass" list).

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
from dataclasses import dataclass
from typing import Any

from pmigrate.triage.collect import collect_raw_failures
from pmigrate.triage.grouping import group_raw_failures
from pmigrate.types import FailureClass, RepoSpec


@dataclass(frozen=True)
class RepoScore:
    repo_id: str
    use_triage: bool  # which ablation arm produced this score (docs/decisions.md D40)
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


def score_run(
    repo: RepoSpec, final_state: Any, wallclock_s: float, *, use_triage: bool
) -> RepoScore:
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

    return RepoScore(
        repo_id=repo.repo_id,
        use_triage=use_triage,
        pass_rate=pass_rate,
        full_green=pass_rate >= 1.0,
        iterations=budget.iterations,
        usd_spent=budget.usd_spent,
        wallclock_s=wallclock_s,
        final_diagnosis_counts=Counter(d.cls for d in diagnoses),
        avg_failures_per_diagnosis=avg_failures_per_diagnosis,
    )
