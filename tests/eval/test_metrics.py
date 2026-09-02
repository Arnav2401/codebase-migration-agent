from typing import Literal

import pytest

from pmigrate.agent.budget import BudgetState
from pmigrate.eval.metrics import score_run
from pmigrate.types import (
    BaselineResult,
    Diagnosis,
    FailureClass,
    RepoSpec,
    TestOutcome,
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
