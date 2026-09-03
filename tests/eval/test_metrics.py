from typing import Literal

import pytest

from pmigrate.agent.budget import BudgetState
from pmigrate.agent.state import RepairAttempt
from pmigrate.eval.metrics import (
    ScoredRepairAttempt,
    classifier_accuracy,
    fix_success_table,
    score_run,
)
from pmigrate.triage.label import LabelledFailure
from pmigrate.types import (
    BaselineResult,
    Diagnosis,
    FailureClass,
    RepoSpec,
    TestOutcome,
    TestRun,
)


def _repo(baseline: BaselineResult | None) -> RepoSpec:
    return RepoSpec(
        repo_id="acme__widgets",
        url="https://example.invalid/acme/widgets",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
        baseline=baseline,
    )


def _baseline(passed: frozenset[str]) -> BaselineResult:
    return BaselineResult(
        passed=passed, failed=frozenset(), skipped=frozenset(), flaky=frozenset(), duration_s=1.0
    )


def _outcome(node_id: str, status: Literal["passed", "failed"]) -> TestOutcome:
    return TestOutcome(node_id, status, 0.1, None if status == "passed" else "boom", None, None)


def test_raises_without_a_captured_baseline() -> None:
    repo = _repo(baseline=None)
    with pytest.raises(ValueError, match="no captured baseline"):
        score_run(repo, {"cumulative_outcomes": {}, "budget": BudgetState()}, 1.0, use_triage=True)


def test_full_green_when_every_baseline_passing_test_still_passes() -> None:
    repo = _repo(_baseline(frozenset({"t.py::a", "t.py::b"})))
    final_state = {
        "cumulative_outcomes": {
            "t.py::a": _outcome("t.py::a", "passed"),
            "t.py::b": _outcome("t.py::b", "passed"),
        },
        "budget": BudgetState(iterations=2, usd_spent=0.5),
        "diagnoses": [],
    }
    score = score_run(repo, final_state, 12.5, use_triage=True)

    assert score.pass_rate == 1.0
    assert score.full_green is True
    assert score.iterations == 2
    assert score.usd_spent == 0.5
    assert score.wallclock_s == 12.5
    assert score.use_triage is True


def test_partial_pass_rate_when_some_baseline_passing_tests_still_fail() -> None:
    repo = _repo(_baseline(frozenset({"t.py::a", "t.py::b"})))
    final_state = {
        "cumulative_outcomes": {
            "t.py::a": _outcome("t.py::a", "passed"),
            "t.py::b": _outcome("t.py::b", "failed"),
        },
        "budget": BudgetState(),
        "diagnoses": [],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.pass_rate == 0.5
    assert score.full_green is False


def test_carries_forward_a_test_not_covered_by_the_final_narrow_run() -> None:
    # docs/decisions.md D46: the exact real bug found on a live corpus run — a test that
    # passed in an EARLIER iteration and was never re-selected for re-testing (because
    # run_tests_node's selection optimization only re-runs previously-failing node_ids)
    # must still count as passing, even though it's absent from the LATEST run.
    repo = _repo(_baseline(frozenset({"t.py::a", "t.py::b", "t.py::c"})))
    final_state = {
        # only "t.py::c" was re-tested in the final iteration (it was the only failure
        # left); "a" and "b" haven't appeared in any run since they were first confirmed
        # passing, but cumulative_outcomes still carries them forward.
        "cumulative_outcomes": {
            "t.py::a": _outcome("t.py::a", "passed"),
            "t.py::b": _outcome("t.py::b", "passed"),
            "t.py::c": _outcome("t.py::c", "failed"),
        },
        "budget": BudgetState(),
        "diagnoses": [],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.pass_rate == pytest.approx(2 / 3)


def test_empty_cumulative_outcomes_scores_as_zero_pass_rate() -> None:
    # a repo that crashed before ever running tests -- shouldn't raise, should score honestly
    repo = _repo(_baseline(frozenset({"t.py::a"})))
    score = score_run(
        repo,
        {"cumulative_outcomes": {}, "budget": BudgetState(), "diagnoses": []},
        1.0,
        use_triage=False,
    )
    assert score.pass_rate == 0.0
    assert score.full_green is False


def _run(outcomes: tuple[TestOutcome, ...]) -> TestRun:
    return TestRun(
        outcomes=outcomes, collection_errors=(), exit_code=1, duration_s=1.0, truncated=False
    )


def test_avg_failures_per_diagnosis_defaults_to_zero_without_a_last_run() -> None:
    # no last_run key at all -- e.g. a repo that crashed before its first test run.
    repo = _repo(_baseline(frozenset({"t.py::a"})))
    score = score_run(
        repo,
        {"cumulative_outcomes": {}, "budget": BudgetState(), "diagnoses": []},
        1.0,
        use_triage=True,
    )
    assert score.avg_failures_per_diagnosis == 0.0


def test_avg_failures_per_diagnosis_is_zero_when_last_run_has_nothing_to_group() -> None:
    # distinct from the "no last_run at all" case above: here a real run happened and
    # everything passed, so there's nothing left to diagnose -- still 0.0, not 1.0.
    repo = _repo(_baseline(frozenset({"t.py::a"})))
    final_state = {
        "cumulative_outcomes": {"t.py::a": _outcome("t.py::a", "passed")},
        "budget": BudgetState(),
        "diagnoses": [],
        "last_run": _run((_outcome("t.py::a", "passed"),)),
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.avg_failures_per_diagnosis == 0.0


def test_avg_failures_per_diagnosis_is_one_when_every_failure_stays_isolated() -> None:
    repo = _repo(_baseline(frozenset()))
    outcomes = (
        TestOutcome(
            "t.py::a", "failed", 0.1, "boom", "app/a.py:1: in x\nE   AssertionError: a", None
        ),
        TestOutcome(
            "t.py::b", "failed", 0.1, "boom", "app/b.py:1: in y\nE   AssertionError: b", None
        ),
    )
    final_state = {
        "cumulative_outcomes": {},
        "budget": BudgetState(),
        "diagnoses": [],
        "last_run": _run(outcomes),
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.avg_failures_per_diagnosis == 1.0


def test_avg_failures_per_diagnosis_reflects_real_grouping() -> None:
    # docs/phase-4-triage.md: "twenty tests failing from one bad import is one problem" --
    # same shared traceback tests/triage/test_grouping.py uses for the grouping logic
    # itself, exercised here through score_run rather than group_raw_failures directly.
    shared_traceback = (
        "fastapi_plugins/settings.py:57: in ConfigManager\n"
        "    def register(self, name: str, config: pydantic.BaseSettings) -> None:\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    repo = _repo(_baseline(frozenset()))
    outcomes = (
        TestOutcome("tests/test_control.py::test_a", "failed", 0.1, "boom", shared_traceback, None),
        TestOutcome("tests/test_logger.py::test_b", "failed", 0.1, "boom", shared_traceback, None),
    )
    final_state = {
        "cumulative_outcomes": {},
        "budget": BudgetState(),
        "diagnoses": [],
        "last_run": _run(outcomes),
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.avg_failures_per_diagnosis == 2.0


def test_final_diagnosis_counts_reflect_state_diagnoses() -> None:
    repo = _repo(_baseline(frozenset({"t.py::a"})))
    diagnoses = [
        Diagnosis(
            node_ids=("t.py::a",),
            cls=FailureClass.IMPORT_ERROR,
            confidence=0.9,
            evidence="x",
            suspect_symbols=(),
            strategy="fix_import",
        ),
        Diagnosis(
            node_ids=("t.py::b",),
            cls=FailureClass.IMPORT_ERROR,
            confidence=0.9,
            evidence="y",
            suspect_symbols=(),
            strategy="fix_import",
        ),
    ]
    score = score_run(
        repo,
        {"cumulative_outcomes": {}, "budget": BudgetState(), "diagnoses": diagnoses},
        1.0,
        use_triage=True,
    )
    assert score.final_diagnosis_counts[FailureClass.IMPORT_ERROR] == 2


def _attempt(
    outcome: str,
    node_ids: tuple[str, ...] = (),
    cls: FailureClass | None = FailureClass.IMPORT_ERROR,
) -> RepairAttempt:
    return RepairAttempt(
        iteration=1,
        cls=cls,
        strategy="fix_import",
        node_ids=node_ids,
        outcome=outcome,
        usd_cost=0.01,  # type: ignore[arg-type]
    )


def test_scored_repairs_marks_an_applied_attempt_fixed_when_all_its_node_ids_pass() -> None:
    repo = _repo(_baseline(frozenset()))
    final_state = {
        "cumulative_outcomes": {
            "t.py::a": _outcome("t.py::a", "passed"),
            "t.py::b": _outcome("t.py::b", "passed"),
        },
        "budget": BudgetState(),
        "diagnoses": [],
        "repair_attempts": [_attempt("applied", node_ids=("t.py::a", "t.py::b"))],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.scored_repairs == (
        ScoredRepairAttempt(attempt=final_state["repair_attempts"][0], fixed=True),
    )


def test_scored_repairs_marks_an_applied_attempt_not_fixed_when_one_node_id_still_fails() -> None:
    repo = _repo(_baseline(frozenset()))
    final_state = {
        "cumulative_outcomes": {
            "t.py::a": _outcome("t.py::a", "passed"),
            "t.py::b": _outcome("t.py::b", "failed"),
        },
        "budget": BudgetState(),
        "diagnoses": [],
        "repair_attempts": [_attempt("applied", node_ids=("t.py::a", "t.py::b"))],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.scored_repairs[0].fixed is False


def test_scored_repairs_never_credits_a_non_applied_outcome_even_if_node_ids_pass() -> None:
    # a "rejected" attempt whose targeted node_ids happen to be passing by the end of the
    # run must NOT be counted fixed -- no code changed in THIS attempt, so crediting it
    # with a fix something else made would be dishonest (docs/decisions.md D51).
    repo = _repo(_baseline(frozenset()))
    final_state = {
        "cumulative_outcomes": {"t.py::a": _outcome("t.py::a", "passed")},
        "budget": BudgetState(),
        "diagnoses": [],
        "repair_attempts": [
            _attempt("rejected", node_ids=("t.py::a",)),
            _attempt("no_edit", node_ids=("t.py::a",)),
            _attempt("no_target", node_ids=("t.py::a",)),
            _attempt("model_error", node_ids=("t.py::a",)),
        ],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert all(scored.fixed is False for scored in score.scored_repairs)


def test_scored_repairs_empty_node_ids_is_never_fixed() -> None:
    # e.g. a no_target attempt where chosen was None and every raw failure was a
    # collection error (node_id=None) -- nothing to check, so never "fixed".
    repo = _repo(_baseline(frozenset()))
    final_state = {
        "cumulative_outcomes": {},
        "budget": BudgetState(),
        "diagnoses": [],
        "repair_attempts": [_attempt("applied", node_ids=())],
    }
    score = score_run(repo, final_state, 1.0, use_triage=True)
    assert score.scored_repairs[0].fixed is False


def test_fix_success_table_aggregates_across_repos_by_class() -> None:
    repo = _repo(_baseline(frozenset()))
    fixed_attempt = _attempt("applied", node_ids=("t.py::a",), cls=FailureClass.CLASS_DEF_ERROR)
    not_fixed_attempt = _attempt("applied", node_ids=("t.py::b",), cls=FailureClass.CLASS_DEF_ERROR)
    score_a = score_run(
        repo,
        {
            "cumulative_outcomes": {"t.py::a": _outcome("t.py::a", "passed")},
            "budget": BudgetState(),
            "diagnoses": [],
            "repair_attempts": [fixed_attempt],
        },
        1.0,
        use_triage=True,
    )
    score_b = score_run(
        repo,
        {
            "cumulative_outcomes": {"t.py::b": _outcome("t.py::b", "failed")},
            "budget": BudgetState(),
            "diagnoses": [],
            "repair_attempts": [not_fixed_attempt],
        },
        1.0,
        use_triage=True,
    )
    table = fix_success_table([score_a, score_b])
    row = table[FailureClass.CLASS_DEF_ERROR]
    assert (row.attempts, row.applied, row.fixed) == (2, 2, 1)
    assert row.fix_rate == pytest.approx(0.5)


def test_fix_success_table_groups_use_triage_false_attempts_under_none() -> None:
    repo = _repo(_baseline(frozenset()))
    score = score_run(
        repo,
        {
            "cumulative_outcomes": {"t.py::a": _outcome("t.py::a", "passed")},
            "budget": BudgetState(),
            "diagnoses": [],
            "repair_attempts": [_attempt("applied", node_ids=("t.py::a",), cls=None)],
        },
        1.0,
        use_triage=False,
    )
    table = fix_success_table([score])
    assert None in table
    assert table[None].fixed == 1


def test_fix_success_table_fix_rate_is_zero_when_nothing_applied() -> None:
    repo = _repo(_baseline(frozenset()))
    score = score_run(
        repo,
        {
            "cumulative_outcomes": {},
            "budget": BudgetState(),
            "diagnoses": [],
            "repair_attempts": [_attempt("no_target", node_ids=())],
        },
        1.0,
        use_triage=True,
    )
    table = fix_success_table([score])
    row = table[FailureClass.IMPORT_ERROR]
    assert (row.attempts, row.applied, row.fixed) == (1, 0, 0)
    assert row.fix_rate == 0.0


def test_fix_success_table_is_empty_for_no_scores() -> None:
    assert fix_success_table([]) == {}


def _labelled(predicted: FailureClass, true: FailureClass) -> LabelledFailure:
    return LabelledFailure(
        repo_id="acme__widgets", node_id="t.py::a", predicted_cls=predicted, true_cls=true, text="x"
    )


def test_classifier_accuracy_is_zero_for_no_labelled_data() -> None:
    # must never look like 100% -- "nothing measured" and "perfect" are not the same thing.
    assert classifier_accuracy([]) == 0.0


def test_classifier_accuracy_is_one_when_every_prediction_matches() -> None:
    labelled = [
        _labelled(FailureClass.IMPORT_ERROR, FailureClass.IMPORT_ERROR),
        _labelled(FailureClass.UNKNOWN, FailureClass.UNKNOWN),
    ]
    assert classifier_accuracy(labelled) == 1.0


def test_classifier_accuracy_reflects_a_partial_match_rate() -> None:
    labelled = [
        _labelled(FailureClass.IMPORT_ERROR, FailureClass.IMPORT_ERROR),
        _labelled(FailureClass.UNKNOWN, FailureClass.VALIDATION_BEHAVIOUR),  # misclassified
        _labelled(FailureClass.CLASS_DEF_ERROR, FailureClass.CLASS_DEF_ERROR),
        _labelled(FailureClass.UNKNOWN, FailureClass.IMPORT_ERROR),  # misclassified
    ]
    assert classifier_accuracy(labelled) == pytest.approx(0.5)
