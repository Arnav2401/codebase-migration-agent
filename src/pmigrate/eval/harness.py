"""Phase 5's eval harness (docs/decisions.md D40/D57) — runs the migration loop across
corpus repos and scores each one via `eval/metrics.py`. `run_repo`/`run_corpus` now take a
full `EvalConfig` rather than a bare `use_triage: bool`; `config.triage` (threaded to
`build_migration_graph`), `config.tiers` (docs/decisions.md D62 — threaded to
`build_migration_graph`'s `enable_t1`, and validated against the caller's own
`model_client`), and `config.usd_cap_per_repo` (the default `BudgetState.usd_cap` when the
caller doesn't pass one explicitly) all affect behavior — `config.model`/`config.seed` are
still carried as provenance on the resulting `RepoResult`, not yet consumed to construct
anything, since the caller already passes a live `model_client` object directly.

`run_corpus`'s `resume: ResumeContext | None` (docs/decisions.md D63) makes it resumable —
a `(repo_id, config_hash(config), resume.corpus_sha)` cell already in `resume.store` is
loaded instead of re-run. `max_workers`/`total_usd_cap` (docs/decisions.md D66) make it
parallel over Docker via a `ThreadPoolExecutor` — `max_workers=1` (the default) keeps the
exact prior sequential control flow, so every existing caller is unaffected.

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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import structlog

from pmigrate.agent.budget import BudgetState
from pmigrate.agent.graph import build_migration_graph
from pmigrate.agent.model_client import ModelClient
from pmigrate.agent.retrieval import (
    Embedder,
    EmbeddingRetrieval,
    GraphRetrieval,
    Retrieval,
    SentenceTransformerEmbedder,
    WholefileRetrieval,
)
from pmigrate.agent.state import AgentState
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.diff_similarity import RepoDiffSimilarity, repo_diff_similarity
from pmigrate.eval.metrics import RepoResult, score_run
from pmigrate.eval.store import ResumeContext, config_hash
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

# guards _dump_residual_failures's shared append-mode file (docs/decisions.md D66) --
# run_corpus's parallel mode can have multiple repos' _run_one_repo calls writing to the
# SAME failures_out path concurrently; without this, two repos' JSONL lines could
# interleave mid-line, since a Python-level `f.write()` per line isn't one atomic OS write.
_failures_out_lock = threading.Lock()


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
    with _failures_out_lock, out_path.open("a") as f:
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


def _build_retrieval(
    config: EvalConfig, repo_id: str, *, embedder: Embedder | None = None
) -> Retrieval:
    """docs/decisions.md D60/D61: constructs the `Retrieval` strategy `config.retrieval`
    actually names. `EvalConfig.__post_init__` already rejects any kind besides the three
    implemented ones at construction time, so the fallback branch here is unreachable in
    practice -- kept as an explicit `ValueError` rather than silently defaulting, so a
    future retrieval kind added to `EvalConfig` without a matching case here fails loudly
    instead of quietly running the wrong strategy.

    `embedder`, when given, is reused as-is instead of constructing a fresh
    `SentenceTransformerEmbedder` (docs/decisions.md D67) -- `run_corpus` builds exactly
    ONE shared instance per run and passes it down here for every repo, so `max_workers>1`
    never races multiple `SentenceTransformer(...)` constructions against each other
    (D67's crash). `embedder=None` (every direct caller/test that isn't `run_corpus`)
    falls back to constructing a fresh one -- cheap, since it's lazy, inside `embed()`,
    not at module load time; only actually constructing and calling this specific class
    pays that cost."""
    if config.retrieval == "graph":
        return GraphRetrieval(repo_id=repo_id)
    if config.retrieval == "wholefile":
        return WholefileRetrieval()
    if config.retrieval == "embedding":
        return EmbeddingRetrieval(embedder=embedder or SentenceTransformerEmbedder())
    raise ValueError(f"no Retrieval implementation wired up for retrieval={config.retrieval!r}")


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
    embedder: Embedder | None = None,
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
    `wallclock_cap_s` for a specific run). `embedder` (docs/decisions.md D67) is passed
    straight through to `_build_retrieval` — `None` unless the caller is `run_corpus`
    sharing one instance across every repo in a `config.retrieval == "embedding"` run."""
    if repo.baseline is None:
        raise ValueError(f"{repo.repo_id} has no captured baseline (I4) — run capture-baselines")
    if "T2" not in config.tiers and model_client is not None:
        # docs/decisions.md D62: config.tiers is the source of truth for which tiers ran
        # — a t1_only config paired with a real model_client would silently contradict
        # itself (repair() would still fire) if this weren't checked here.
        raise ValueError(
            f"config.tiers={set(config.tiers)!r} excludes T2/T3 but a real model_client "
            "was passed — pass model_client=None for a t1_only config"
        )

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
        retrieval=_build_retrieval(config, repo.repo_id, embedder=embedder),
        enable_t1="T1" in config.tiers,
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


class _GlobalBudgetTracker:
    """Thread-safe running total for `run_corpus`'s optional `total_usd_cap`
    (docs/decisions.md D66) — checked before STARTING a new repo, not enforced by killing
    an in-flight one. A repo already running when the cap is hit finishes normally rather
    than being cut off mid-Docker-run: cancelling a live container cleanly (killing the
    process group, reclaiming partial trace/edit state) is a materially bigger feature
    than "parallelism with a cost cap" calls for, so the possible overshoot — up to
    `max_workers` repos' worth of already-in-flight spending — is a named limitation, not
    something silently approximated by a check that looks precise but isn't."""

    def __init__(self, cap: float) -> None:
        self._cap = cap
        self._spent = 0.0
        self._lock = threading.Lock()

    def exhausted(self) -> bool:
        with self._lock:
            return self._spent >= self._cap

    def add(self, usd: float) -> None:
        with self._lock:
            self._spent += usd


def _run_one_repo(
    repo: RepoSpec,
    *,
    work_root: Path,
    sandbox: Sandbox,
    model_client: ModelClient | None,
    config: EvalConfig,
    split: Literal["dev", "test"] | None,
    policy: SandboxPolicy | None,
    budget: BudgetState | None,
    failures_out: Path | None,
    resume: ResumeContext | None,
    budget_tracker: _GlobalBudgetTracker | None,
    embedder: Embedder | None,
) -> RepoResult | None:
    """One repo's worth of `run_corpus`'s loop body — factored out so both the sequential
    path (`max_workers=1`, identical control flow to before docs/decisions.md D66) and the
    `ThreadPoolExecutor` path call the exact same logic. Returns `None` for every "skip
    this repo" case (no baseline, wrong split, global budget exhausted, or a real failure)
    so both callers share one "only keep non-None results" rule. `embedder` (docs/decisions.md
    D67) is `run_corpus`'s one shared `SentenceTransformerEmbedder` instance when
    `config.retrieval == "embedding"`, threaded straight through to `run_repo` — never
    constructed here, so every worker thread reuses the same instance instead of racing
    to build its own."""
    if repo.baseline is None:
        log.info("harness.skip_no_baseline", repo_id=repo.repo_id)
        return None
    if split is not None and repo.split != split:
        return None

    if resume is not None:
        c_hash = config_hash(config)
        if resume.store.has_result(repo.repo_id, c_hash, resume.corpus_sha):
            existing = resume.store.load_result(repo.repo_id, c_hash, resume.corpus_sha)
            if existing is not None:
                log.info("harness.skip_already_scored", repo_id=repo.repo_id)
                return existing

    if budget_tracker is not None and budget_tracker.exhausted():
        log.info("harness.skip_global_budget_exhausted", repo_id=repo.repo_id)
        return None

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
            embedder=embedder,
        )
    except Exception as e:
        log.warning("harness.repo_failed", repo_id=repo.repo_id, error=str(e))
        return None

    if resume is not None:
        resume.store.save_result(result, resume.corpus_sha, written_at=time.time())
    if budget_tracker is not None:
        budget_tracker.add(result.usd_spent)

    log.info(
        "harness.repo_scored",
        repo_id=repo.repo_id,
        config=config.name,
        triage=config.triage,
        pass_rate=result.pass_rate,
        full_green=result.full_green,
        usd_spent=result.usd_spent,
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
    resume: ResumeContext | None = None,
    max_workers: int = 1,
    total_usd_cap: float | None = None,
) -> list[RepoResult]:
    """One repo's failure (clone, build, or a crash mid-loop) is logged and skipped, not
    fatal to the rest — matching capture_baselines.py's own additive-not-destructive
    stance on a single bad repo.

    `resume` (docs/decisions.md D63): when set, a `(repo_id, config_hash, corpus_sha)`
    cell already in `resume.store` is loaded and returned WITHOUT re-checkout/build/run —
    the whole point of resumability is skipping that expensive work, not just skipping
    the scoring at the end.

    `max_workers`/`total_usd_cap` (docs/decisions.md D66): `max_workers=1` (the default)
    runs the exact sequential control flow this function always has — same log ordering,
    same "one repo builds while another's Docker call is still running" NEVER happening —
    so every existing caller/test is unaffected. `max_workers>1` runs repos concurrently
    via a `ThreadPoolExecutor` (I/O-bound work: git clone, Docker, LLM HTTP calls all
    release the GIL while waiting), matching phase-5-eval.md's "parallel over Docker with
    a concurrency cap that matches your machine." `total_usd_cap`, if given, stops
    STARTING new repos once the running total already spent meets or exceeds it — see
    `_GlobalBudgetTracker`'s own docstring for why an in-flight repo isn't cut off.

    `embedder` (docs/decisions.md D67): built ONCE here, before either dispatch path, and
    passed to every `_run_one_repo`/`run_repo` call for the whole corpus — `None` unless
    `config.retrieval == "embedding"`, in which case one shared `SentenceTransformerEmbedder`
    replaces the old one-per-repo construction that crashed the process outright under
    `max_workers>1` (concurrent `SentenceTransformer(...)` construction, see D67). The
    instance itself is cheap to construct (no model load yet — that's still lazy, inside
    `embed()`); its own internal lock (`retrieval.py`) is what makes sharing it across
    `ThreadPoolExecutor` worker threads safe."""
    if max_workers < 1:
        raise ValueError(f"max_workers must be >= 1, got {max_workers}")

    budget_tracker = _GlobalBudgetTracker(total_usd_cap) if total_usd_cap is not None else None
    embedder: Embedder | None = (
        SentenceTransformerEmbedder() if config.retrieval == "embedding" else None
    )

    if max_workers == 1:
        results = []
        for repo in specs:
            result = _run_one_repo(
                repo,
                work_root=work_root,
                sandbox=sandbox,
                model_client=model_client,
                config=config,
                split=split,
                policy=policy,
                budget=budget,
                failures_out=failures_out,
                resume=resume,
                budget_tracker=budget_tracker,
                embedder=embedder,
            )
            if result is not None:
                results.append(result)
        return results

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _run_one_repo,
                repo,
                work_root=work_root,
                sandbox=sandbox,
                model_client=model_client,
                config=config,
                split=split,
                policy=policy,
                budget=budget,
                failures_out=failures_out,
                resume=resume,
                budget_tracker=budget_tracker,
                embedder=embedder,
            )
            for repo in specs
        ]
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
    return results
