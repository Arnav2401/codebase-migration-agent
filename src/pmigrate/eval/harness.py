"""Phase 4's minimal eval harness (docs/decisions.md D40) — runs the migration loop
across corpus repos and scores each one via `eval/metrics.py`. Deliberately NOT Phase
5's full `EvalConfig`/ablation-arm harness (interfaces.md §8: retrieval strategy, tiers,
seed, resumable parallel Docker runs) — this hard-codes one axis (`use_triage`) because
that's the one axis phase-4-triage.md's own acceptance criteria need measured.

Split for testability (CLAUDE.md: no network in unit tests): `run_repo` takes an
ALREADY-checked-out `source_root` and a pre-built `image`, so it can be exercised with
`FakeSandbox`/`FakeModelClient` exactly like `tests/agent/test_graph.py` does. Only
`checkout_pre_sha` and `run_corpus`'s orchestration loop touch git/Docker for real —
exercised by a live corpus run, not pytest (the same split `capture_baselines.py`'s own
tests already draw around real Docker calls).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import structlog

from pmigrate.agent.budget import BudgetState
from pmigrate.agent.graph import build_migration_graph
from pmigrate.agent.model_client import ModelClient
from pmigrate.agent.state import AgentState
from pmigrate.eval.metrics import RepoScore, score_run
from pmigrate.graph.relevance import compute_work_list
from pmigrate.graph.repo_files import read_py_files
from pmigrate.graph.resolver import resolve_repo
from pmigrate.sandbox.protocol import Sandbox
from pmigrate.triage.collect import collect_raw_failures
from pmigrate.triage.grouping import group_raw_failures
from pmigrate.types import ImageRef, RepoSpec, SandboxPolicy

log = structlog.get_logger()

CLONE_TIMEOUT_S = 300
CHECKOUT_TIMEOUT_S = 60


def checkout_pre_sha(repo: RepoSpec, dest: Path) -> None:
    """Real network I/O — not unit-tested (see module docstring). `run_repo` takes the
    already-checked-out result so it stays testable without git.

    Removes `dest` first if it already exists — matching `corpus/validate.py`'s
    `_clone_shallow` — so re-running the harness against the same `work_root` (a repeat
    corpus run, an interrupted earlier attempt) doesn't fail `git clone` with "destination
    path already exists and is not an empty directory."""
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(
        ["git", "clone", "--quiet", repo.url, str(dest)],
        check=True,
        capture_output=True,
        timeout=CLONE_TIMEOUT_S,
    )
    subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", repo.pre_sha],
        check=True,
        capture_output=True,
        timeout=CHECKOUT_TIMEOUT_S,
    )


def _dump_residual_failures(repo: RepoSpec, final_state: Any, out_path: Path) -> None:
    """Appends every failure still standing at the end of the run, paired with the
    classifier's predicted class and the FULL raw failure text (not `Diagnosis.evidence`'s
    ~200-char snippet, which is already answer-revealing — useless as blind hand-labelling
    input). Seed data for phase-4-triage.md's "≥100 hand-labelled real failures"
    requirement; the labelling/accuracy-scoring step itself is future work once this file
    has real content in it."""
    last_run = final_state.get("last_run")
    if last_run is None:
        return
    grouped = group_raw_failures(collect_raw_failures(last_run), repo.baseline)
    with out_path.open("a") as f:
        for g in grouped:
            for raw in g.raw_failures:
                f.write(
                    json.dumps(
                        {
                            "repo_id": repo.repo_id,
                            "node_id": raw.node_id,
                            "predicted_cls": g.diagnosis.cls.value,
                            "text": raw.text,
                        }
                    )
                    + "\n"
                )


def run_repo(
    repo: RepoSpec,
    *,
    image: ImageRef,
    source_root: Path,
    overlay_root: Path,
    sandbox: Sandbox,
    model_client: ModelClient | None,
    use_triage: bool = True,
    policy: SandboxPolicy | None = None,
    budget: BudgetState | None = None,
    failures_out: Path | None = None,
) -> RepoScore:
    """Runs the full migration loop against one already-checked-out repo and scores the
    result. `image` is built by the caller (`sandbox.build(repo, "v2")` — the SAME image
    is reused for every `run_tests` call across the whole loop, so it must already have
    pydantic v2 installed: T1/T2 progressively rewrite the *source* from v1 to v2 syntax
    against a constant v2-pinned environment, they don't swap the image mid-run. "v1" is
    only ever `capture_baselines.py`'s own separate baseline-measurement flow — building
    this harness's image at "v1" instead was a real bug caught live, docs/decisions.md
    D42: T1's `ConfigDict`/`pydantic_settings` rewrite then had nothing installed to
    import, breaking collection for every module that touched the rewritten file).
    Cached by `sandbox/image.py`'s deps-hash rather than built here, matching
    `build_migration_graph`'s own build-vs-run split. `budget` defaults to
    `BudgetState()`'s own defaults ($5 usd_cap, 20 max_iterations) if not given — a live
    corpus run should usually pass a tighter cap explicitly."""
    if repo.baseline is None:
        raise ValueError(f"{repo.repo_id} has no captured baseline (I4) — run capture-baselines")

    resolved = resolve_repo(read_py_files(source_root))
    work_list = compute_work_list(resolved, repo.repo_id)

    graph = build_migration_graph(
        sandbox=sandbox,
        image=image,
        source_root=source_root,
        overlay_root=overlay_root,
        policy=policy or SandboxPolicy(),
        model_client=model_client,
        use_triage=use_triage,
    )

    start = time.time()
    state = AgentState(repo=repo, work_list=work_list, budget=budget or BudgetState())
    final_state = graph.invoke(state)
    wallclock_s = time.time() - start

    if failures_out is not None:
        _dump_residual_failures(repo, final_state, failures_out)

    return score_run(repo, final_state, wallclock_s, use_triage=use_triage)


def run_corpus(
    specs: list[RepoSpec],
    *,
    work_root: Path,
    sandbox: Sandbox,
    model_client: ModelClient | None,
    split: Literal["dev", "test"] | None = "dev",
    use_triage: bool = True,
    policy: SandboxPolicy | None = None,
    budget: BudgetState | None = None,
    failures_out: Path | None = None,
) -> list[RepoScore]:
    """One repo's failure (clone, build, or a crash mid-loop) is logged and skipped, not
    fatal to the rest — matching capture_baselines.py's own additive-not-destructive
    stance on a single bad repo."""
    scores = []
    for repo in specs:
        if repo.baseline is None:
            log.info("harness.skip_no_baseline", repo_id=repo.repo_id)
            continue
        if split is not None and repo.split != split:
            continue

        repo_root = work_root / repo.repo_id
        source_root = repo_root / "source"
        overlay_root = repo_root / "overlay"
        # fresh every run (docs/decisions.md D45): edit_t1 only writes a file into
        # overlay_root if it doesn't already exist there, so a stale overlay left over
        # from an earlier run at this same work_root would already contain the PREVIOUS
        # run's T1/T2 edits already applied — apply_rules would then see before==after
        # (nothing left to change) and silently report edits_applied=0, understating what
        # T1 actually does on a genuinely fresh checkout. Found live: a re-run against the
        # same work_root reused a prior run's already-migrated overlay content.
        if overlay_root.exists():
            shutil.rmtree(overlay_root)
        overlay_root.mkdir(parents=True)

        try:
            checkout_pre_sha(repo, source_root)
            image = sandbox.build(repo, "v2")
            # a fresh started_at per repo — reusing one BudgetState instance across every
            # repo in the loop would make wallclock_cap_s count from the FIRST repo's
            # start, not each repo's own, and falsely trip on a later repo in a long run.
            repo_budget = replace(budget, started_at=time.time()) if budget else None
            score = run_repo(
                repo,
                image=image,
                source_root=source_root,
                overlay_root=overlay_root,
                sandbox=sandbox,
                model_client=model_client,
                use_triage=use_triage,
                policy=policy,
                budget=repo_budget,
                failures_out=failures_out,
            )
        except Exception as e:
            log.warning("harness.repo_failed", repo_id=repo.repo_id, error=str(e))
            continue

        scores.append(score)
        log.info(
            "harness.repo_scored",
            repo_id=repo.repo_id,
            use_triage=use_triage,
            pass_rate=score.pass_rate,
            full_green=score.full_green,
            usd_spent=score.usd_spent,
        )

    return scores
