from collections import Counter

import pytest

from pmigrate.agent.confidence import ConfidenceInputs, score
from pmigrate.pr import ForkTargetError, assert_allowed_target, build_pr_body, is_allowed_target
from pmigrate.pr.body import NEEDS_REVIEW_BELOW, plan_from_trace
from pmigrate.trace.events import TraceEvent


def _ev(kind, payload, **kw):  # type: ignore[no-untyped-def]
    return TraceEvent(
        run_id="r1", span_id="s", parent_span=None, ts=0.0, kind=kind, payload=payload, **kw
    )


# --- I7: fork-only ---------------------------------------------------------------------


def test_upstream_targets_are_refused_in_every_url_form() -> None:
    """I7 is the invariant most likely to embarrass this project in public, so the guard is
    checked against each shape a target can arrive in."""
    for upstream in (
        "pydantic/pydantic",
        "https://github.com/lnbits/lnurl",
        "git@github.com:Aiven-Open/rohmu.git",
        "https://github.com/Arnav2401Evil/rohmu",  # prefix-similar, still not the owner
    ):
        assert not is_allowed_target(upstream)
        with pytest.raises(ForkTargetError, match=r"REFUSING to target|cannot parse"):
            assert_allowed_target(upstream)


def test_owned_forks_are_allowed_in_every_url_form() -> None:
    for mine in (
        "Arnav2401/rohmu",
        "https://github.com/Arnav2401/rohmu",
        "git@github.com:Arnav2401/rohmu.git",
    ):
        assert is_allowed_target(mine)
        assert assert_allowed_target(mine) == ("Arnav2401", "rohmu")


def test_unparseable_targets_refuse_rather_than_pass() -> None:
    """A target the guard cannot understand must fail closed."""
    assert not is_allowed_target("not a repo")
    with pytest.raises(ForkTargetError):
        assert_allowed_target("not a repo")


# --- body generated from the trace ------------------------------------------------------


def _trace() -> list[TraceEvent]:
    return [
        _ev("phase", {"name": "run_repo.start"}),
        _ev("test_run", {"passed": 2, "total": 20, "iteration": 1}),
        _ev("triage", {"classes": ["import_error"]}),
        _ev(
            "patch",
            {
                "source": "T1",
                "outcome": "applied",
                "files_changed": ["a.py"],
                "lines_changed": 30,
                "rules_fired": ["dict_to_model_dump"],
            },
        ),
        _ev("llm_call", {"model": "m", "purpose": "repair"}, tokens_in=10, tokens_out=5, usd=0.01),
        _ev(
            "patch",
            {"source": "T2", "outcome": "applied", "files_changed": ["b.py"], "lines_changed": 10},
        ),
        _ev(
            "patch",
            {"source": "T2", "outcome": "rejected", "files_changed": [], "lines_changed": 0},
        ),
        _ev("test_run", {"passed": 18, "total": 20, "iteration": 3}),
    ]


def test_plan_reconstructs_the_whole_run_from_events_alone() -> None:
    p = plan_from_trace(_trace())
    assert p.first_tests == (2, 20)
    assert p.last_tests == (18, 20)
    assert p.iterations == 3
    assert p.files_by_source == {"T1": ["a.py"], "T2": ["b.py"]}
    assert p.lines_by_source == {"T1": 30, "T2": 10}  # rejected patch contributes nothing
    assert p.rules_fired == ["dict_to_model_dump"]
    assert p.usd == pytest.approx(0.01)


def test_body_does_not_call_the_first_measurement_a_baseline() -> None:
    """The agent's first test run happens AFTER T1 has already edited, so labelling it
    "before" would overstate what the PR changed (docs/decisions.md D94)."""
    body = build_pr_body(
        plan_from_trace(_trace()),
        score(ConfidenceInputs(mechanical_lines=30, model_lines=10)),
        repo_id="acme__widgets",
    )
    assert "after T1 codemods" in body
    assert "- before:" not in body


def test_body_reports_before_and_after_and_names_both_sources() -> None:
    p = plan_from_trace(_trace())
    s = score(
        ConfidenceInputs(
            mechanical_lines=30, model_lines=10, iterations=3, diagnosis_counts=Counter()
        )
    )
    body = build_pr_body(p, s, repo_id="acme__widgets")
    assert "2/20" in body and "18/20" in body
    assert "Deterministic codemods (T1)" in body
    assert "Model-written repair (T2/T3)" in body
    assert "`dict_to_model_dump`" in body
    assert "pmigrate replay r1" in body


def test_a_low_confidence_run_leads_with_the_review_warning() -> None:
    """An automated PR that buries its own uncertainty is worse than one that never opened,
    so the warning goes above the diff summary, not below it."""
    p = plan_from_trace(_trace())
    low = score(ConfidenceInputs(mechanical_lines=0, model_lines=100, iterations=19))
    assert low.value < NEEDS_REVIEW_BELOW
    body = build_pr_body(p, low, repo_id="acme__widgets")
    assert body.index("Needs human review") < body.index("What changed")
    assert "over-confident" in body  # cites this project's own calibration finding


def test_unpriced_calls_make_the_cost_a_stated_lower_bound() -> None:
    events = [_ev("llm_call", {"model": "m"}, tokens_in=1, tokens_out=1)]  # no usd
    body = build_pr_body(plan_from_trace(events), score(ConfidenceInputs()), repo_id="x")
    assert "lower bound" in body
