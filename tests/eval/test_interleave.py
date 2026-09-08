from dataclasses import replace

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.interleave import budget_exhausted_repos, interleaved_plan
from pmigrate.types import RepoSpec


def _repo(repo_id: str) -> RepoSpec:
    return RepoSpec(
        repo_id=repo_id,
        url=f"https://example.invalid/{repo_id}",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=["pip", "install", "-e", "."],
        test_cmd=["pytest", "-q"],
        setup_overrides=(),
        split="dev",
        baseline=None,
        human_diff_stats=None,
    )


def _configs() -> list[EvalConfig]:
    base = EvalConfig(name="graph", model="m")
    return [base, replace(base, name="embedding"), replace(base, name="wholefile")]


def test_all_arms_run_on_a_repo_before_the_next_repo_starts() -> None:
    """The confound this fixes (docs/decisions.md D102): back-to-back arms spend a shared
    daily budget in run order, so the first arm landed 7 repairs, the second 1, the third
    0 -- a ranking of who ran first, not of which retrieval strategy is better."""
    repos = [_repo("a"), _repo("b")]
    plan = interleaved_plan(repos, _configs())

    assert [r.repo_id for r, _ in plan[:3]] == ["a", "a", "a"]
    assert [r.repo_id for r, _ in plan[3:]] == ["b", "b", "b"]


def test_arm_order_rotates_so_no_arm_is_always_first() -> None:
    """Even within a repo, going first is an advantage when budget is scarce. Rotating
    means a budget that dies partway cannot be systematically kind to one arm."""
    plan = interleaved_plan([_repo("a"), _repo("b"), _repo("c")], _configs())
    firsts = [
        c.name
        for (r, c), prev in zip(plan, [None, *plan], strict=False)
        if prev is None or prev[0] != r
    ]
    assert firsts == ["graph", "embedding", "wholefile"]


def test_every_repo_arm_pair_appears_exactly_once() -> None:
    repos = [_repo("a"), _repo("b")]
    plan = interleaved_plan(repos, _configs())
    pairs = [(r.repo_id, c.name) for r, c in plan]
    assert len(pairs) == len(set(pairs)) == 6


def test_partially_scored_repos_are_identified_for_exclusion() -> None:
    """An arm that never ran on a repo contributes no evidence about it. Including the arms
    that DID would compare a full set against a partial one -- the same confound, moved to
    analysis time."""
    plan = interleaved_plan([_repo("a"), _repo("b")], _configs())
    scored = {("a", "graph"), ("a", "embedding"), ("a", "wholefile"), ("b", "graph")}

    assert budget_exhausted_repos(plan, scored) == {"b"}


def test_a_repo_no_arm_reached_is_not_flagged_as_partial() -> None:
    """Untouched is not partial: it simply contributes nothing, and flagging it would
    imply a comparison was spoiled when none was attempted."""
    plan = interleaved_plan([_repo("a"), _repo("b")], _configs())
    assert (
        budget_exhausted_repos(plan, {("a", "graph"), ("a", "embedding"), ("a", "wholefile")})
        == set()
    )


def test_empty_config_list_yields_no_plan() -> None:
    assert interleaved_plan([_repo("a")], []) == []
