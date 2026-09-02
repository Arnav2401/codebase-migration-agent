"""The migration loop's state (docs/interfaces.md §5). A plain dataclass, not frozen —
LangGraph's node functions return partial-update dicts that it merges into a fresh state
object between steps (verified interactively: a node returning `{"cursor": n}` updates
just that field, so nodes never need to reconstruct or mutate the whole state by hand).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pmigrate.agent.budget import BudgetState
from pmigrate.codemod.protocol import RuleEdit
from pmigrate.types import Diagnosis, MigrationUnit, RepoSpec, TestOutcome, TestRun

Status = Literal["running", "done", "budget_exceeded", "no_progress", "failed"]
EditSource = Literal["T1", "T2", "T3"]


@dataclass(frozen=True)
class Edit:
    source: EditSource
    unit_module: str
    files_changed: tuple[str, ...]
    diff: str
    rule_edits: tuple[RuleEdit, ...] = ()  # populated for T1; empty for T2/T3


@dataclass
class AgentState:
    repo: RepoSpec
    work_list: list[list[MigrationUnit]]
    cursor: int = 0
    edits: list[Edit] = field(default_factory=list)
    last_run: TestRun | None = None
    # docs/decisions.md D46: `last_run` is deliberately the NARROW per-iteration view —
    # after the first call, `run_tests_node`'s `selection` optimization only re-tests
    # previously-failing node_ids, so `last_run.outcomes` stops covering the whole suite.
    # That's exactly right for route()/classify_node/NoProgressDetector, which only care
    # about what's CURRENTLY failing — but it's wrong for scoring (eval/metrics.py),
    # which needs to know the full set of baseline-passing tests still passing, most of
    # which were never re-tested after the first iteration. `cumulative_outcomes` is a
    # separate, purely additive accounting field for exactly that: every node_id's most
    # recently OBSERVED outcome, carried forward when a later run doesn't re-test it.
    cumulative_outcomes: dict[str, TestOutcome] = field(default_factory=dict)
    diagnoses: list[Diagnosis] = field(default_factory=list)
    iteration: int = 0
    budget: BudgetState = field(default_factory=BudgetState)
    trace_id: str = ""
    status: Status = "running"

    @property
    def current_batch(self) -> list[MigrationUnit] | None:
        """None once the cursor has moved past every batch — the only correct way to ask
        "is there more work". An earlier `is_last_batch` property (`cursor >= len - 1`)
        looked plausible but was actually wrong: after edit_t1 finishes batch 0 of 2 and
        advances the cursor to 1, `1 >= 2 - 1` is already True, incorrectly reporting
        "last batch" one batch early and skipping the real last batch entirely. Caught by
        a two-unit test in test_graph.py, not by inspection."""
        if self.cursor >= len(self.work_list):
            return None
        return self.work_list[self.cursor]
