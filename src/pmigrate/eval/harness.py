"""Phase 5's eval harness (docs/decisions.md D40/D57) — runs the migration loop across
corpus repos and scores each one via `eval/metrics.py`. Still NOT the full resumable,
parallel, SQLite-backed harness interfaces.md §8/phase-5-eval.md describe — that's a
later Phase 5 step, built once `EvalConfig`/`RepoResult` (this step) have real callers.
`run_repo`/`run_corpus` now take a full `EvalConfig` rather than a bare `use_triage: bool`,
but only `config.triage` (threaded to `build_migration_graph`) and
`config.usd_cap_per_repo` (the default `BudgetState.usd_cap` when the caller doesn't pass
one explicitly) actually affect behavior yet — `config.model`/`config.seed` are carried as
provenance on the resulting `RepoResult`, not yet consumed to construct anything, since the
caller already passes a live `model_client` object directly.

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
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.diff_similarity import RepoDiffSimilarity, repo_diff_similarity
from pmigrate.eval.metrics import RepoResult, score_run
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


def _read_text_or_empty(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _git_show(repo_root: Path, sha: str, path: str) -> str:
    """Content of `path` at `sha` inside the repo already cloned at `repo_root` -- "" if
    the file doesn't exist at that sha (added later by the human's real fix, or already
    deleted before `pre_sha`). A clean git failure here means "file absent," not a real
    error to propagate; `checkout_pre_sha`'s `git clone` is a full (not shallow) clone, so
    `post_sha` is already present in this same local history -- no second checkout."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 else ""


def _agent_touched_files(final_state: Any) -> set[str]:
    touched: set[str] = set()
    for edit in final_state.get("edits", []):
        touched.update(edit.files_changed)
    return touched


def compute_diff_similarity(
    repo: RepoSpec, source_root: Path, overlay_root: Path, final_state: Any
) -> RepoDiffSimilarity | None:
    """docs/decisions.md D58: `None` (not a fabricated 0.0/1.0) when there's nothing real
    to measure -- no `human_diff_stats` on this `RepoSpec` (docs/decisions.md: "used as
    ground truth in Phase 5"), or neither side touched any Python file. A missing
    measurement must stay visibly missing, not look like a real, if poor, score.

    Compares the UNION of (files the agent touched, from `final_state["edits"]`) and
    (files the human's real fix touched, from `RepoSpec.human_diff_stats.changed_paths` --
    already-validated ground truth from `corpus/validate.py`, not recomputed via a fresh
    `git diff`). A file only one side touched still belongs in the comparison, with the
    untouched side's content equal to `before` — that's what correctly penalizes a file
    the human fixed that the agent never tried, and a file the agent touched that the
    human's real fix never needed."""
    if repo.human_diff_stats is None:
        return None
    human_files = {p for p in repo.human_diff_stats.changed_paths if p.endswith(".py")}
    all_files = human_files | _agent_touched_files(final_state)
    if not all_files:
        return None

    file_tuples = []
    for path in sorted(all_files):
        before = _read_text_or_empty(source_root / path)
        overlay_path = overlay_root / path
        agent_after = _read_text_or_empty(overlay_path) if overlay_path.exists() else before
        human_after = _git_show(source_root, repo.post_sha, path)
        file_tuples.append((path, before, agent_after, human_after))

    return repo_diff_similarity(file_tuples)


def run_repo(
    repo: RepoSpec,
    *,
    image: ImageRef,
    source_root: Path,
    overlay_root: Path,
    sandbox: Sandbox,
    model_client: ModelClient | None,
    config: EvalConfig,
    policy: SandboxPolicy | None = None,
    budget: BudgetState | None = None,
    failures_out: Path | None = None,
) -> RepoResult:
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
    `BudgetState(usd_cap=config.usd_cap_per_repo)` if not given — pass one explicitly for
    anything besides `config`'s own cap (e.g. a tighter `max_iterations` or
    `wallclock_cap_s` for a specific run)."""
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
        use_triage=config.triage,
    )

    start = time.time()
    state = AgentState(
        repo=repo,
        work_list=work_list,
        budget=budget or BudgetState(usd_cap=config.usd_cap_per_repo),
    )
    final_state = graph.invoke(state)
    wallclock_s = time.time() - start

    if failures_out is not None:
        _dump_residual_failures(repo, final_state, failures_out)

    result = score_run(repo, final_state, wallclock_s, config=config)

    similarity = compute_diff_similarity(repo, source_root, overlay_root, final_state)
    if similarity is not None:
        result = replace(
            result,
            diff_line_jaccard=similarity.line_jaccard,
            symbol_precision=similarity.symbol_precision,
            symbol_recall=similarity.symbol_recall,
        )

    return result


def run_corpus(
    specs: list[RepoSpec],
    *,
    work_root: Path,
    sandbox: Sandbox,
    model_client: ModelClient | None,
    config: EvalConfig,
    split: Literal["dev", "test"] | None = "dev",
    policy: SandboxPolicy | None = None,
    budget: BudgetState | None = None,
    failures_out: Path | None = None,
) -> list[RepoResult]:
    """One repo's failure (clone, build, or a crash mid-loop) is logged and skipped, not
    fatal to the rest — matching capture_baselines.py's own additive-not-destructive
    stance on a single bad repo."""
    results = []
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
            result = run_repo(
                repo,
                image=image,
                source_root=source_root,
                overlay_root=overlay_root,
                sandbox=sandbox,
                model_client=model_client,
                config=config,
                policy=policy,
                budget=repo_budget,
                failures_out=failures_out,
            )
        except Exception as e:
            log.warning("harness.repo_failed", repo_id=repo.repo_id, error=str(e))
            continue

        results.append(result)
        log.info(
            "harness.repo_scored",
            repo_id=repo.repo_id,
            config=config.name,
            triage=config.triage,
            pass_rate=result.pass_rate,
            full_green=result.full_green,
            usd_spent=result.usd_spent,
        )

    return results
