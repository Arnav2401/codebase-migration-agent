"""Interleaved multi-arm execution, so a shared provider budget cannot decide the ablation.

**The problem this exists for (docs/decisions.md D102).** Running arms back to back —
`graph`, then `embedding`, then `wholefile` — spends a shared daily token budget in run
order. Measured live: the first arm landed 7 repairs, the second 1, the third 0, every
failure a 429, and the resulting "graph > embedding > wholefile" ranking was a ranking of
who ran first. Six earlier attempts at this ablation (D87) failed the same way without the
cause being visible, because each arm was launched as a separate command.

**The fix is to interleave by repo.** For each repo, run every arm before moving on. The
budget still runs out, but it runs out *between repos* rather than *between arms*, so the
arms being compared on any given repo saw comparable conditions. An ablation is a
within-repo comparison; the execution order should match.

**Arm order is rotated per repo** so that even the residual within-repo advantage of going
first is not always handed to the same arm.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from pmigrate.eval.config import EvalConfig
from pmigrate.types import RepoSpec


def interleaved_plan(
    repos: Iterable[RepoSpec], configs: list[EvalConfig]
) -> list[tuple[RepoSpec, EvalConfig]]:
    """(repo, config) pairs in the order they should execute.

    Groups by repo, and rotates the arm order for each successive repo so no arm is
    systematically first. With 3 arms and 7 repos, each arm leads at least twice, so a
    budget that dies partway through cannot be systematically kind to one of them.
    """
    if not configs:
        return []
    plan: list[tuple[RepoSpec, EvalConfig]] = []
    order: deque[EvalConfig] = deque(configs)
    for repo in repos:
        plan.extend((repo, config) for config in order)
        order.rotate(-1)  # next repo starts with the arm that went second here
    return plan


def budget_exhausted_repos(
    plan: list[tuple[RepoSpec, EvalConfig]], scored: set[tuple[str, str]]
) -> set[str]:
    """Repos where at least one arm ran but not all of them.

    These are exactly the repos that must be EXCLUDED from a cross-arm comparison: an arm
    that never ran on a repo contributes no evidence about it, and including the arms that
    did would compare a full set against a partial one -- the confound this module exists
    to prevent, reintroduced at analysis time.
    """
    per_repo: dict[str, set[str]] = {}
    for repo, config in plan:
        per_repo.setdefault(repo.repo_id, set()).add(config.name)
    partial: set[str] = set()
    for repo_id, arms in per_repo.items():
        ran = {arm for arm in arms if (repo_id, arm) in scored}
        if ran and ran != arms:
            partial.add(repo_id)
    return partial
