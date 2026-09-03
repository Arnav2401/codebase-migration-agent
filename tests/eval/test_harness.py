import json
import subprocess
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from pmigrate.agent.model_client import FakeModelClient, ModelResponse
from pmigrate.agent.retrieval import GraphRetrieval, WholefileRetrieval
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.harness import _build_retrieval, run_corpus, run_repo
from pmigrate.eval.store import ResultStore, ResumeContext, config_hash
from pmigrate.types import (
    BaselineResult,
    ImageRef,
    RepoSpec,
    SandboxPolicy,
    TestOutcome,
    TestRun,
)


def _config(triage: bool = True) -> EvalConfig:
    return EvalConfig(name="test", model="fake", triage=triage)


@dataclass
class FakeSandbox:
    """Same role as tests/agent/test_graph.py's FakeSandbox, plus a real `build()` —
    run_repo calls it directly (unlike agent/graph.py, which takes a pre-built image)."""

    responses: list[TestRun]
    run_calls: list = field(default_factory=list)
    _index: int = 0

    def build(self, repo, pydantic):  # type: ignore[no-untyped-def]
        return ImageRef(
            tag=f"{repo.repo_id}-{pydantic}",
            repo_id=repo.repo_id,
            sha=repo.pre_sha,
            pydantic=pydantic,
            deps_hash="x",
            test_cmd=repo.test_cmd,
        )

    def run_tests(self, image, workdir_overlay, policy, selection=None):  # type: ignore[no-untyped-def]
        self.run_calls.append(selection)
        response = self.responses[min(self._index, len(self.responses) - 1)]
        self._index += 1
        return response


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


def _passed_run(node_id: str = "t.py::test_a") -> TestRun:
    return TestRun(
        outcomes=(TestOutcome(node_id, "passed", 0.1, None, None, None),),
        collection_errors=(),
        exit_code=0,
        duration_s=0.1,
        truncated=False,
    )


def _failed_run(
    node_id: str = "t.py::test_a",
    traceback: str = "app/models.py:1: in <module>\n    x = 1\nE   AssertionError: boom",
) -> TestRun:
    # a realistic traceback (a first-party path repair.extract_target_file can actually
    # find), matching tests/agent/test_graph.py's own _failed_run -- repair() declines to
    # call the model at all without a findable target file.
    return TestRun(
        outcomes=(TestOutcome(node_id, "failed", 0.1, "boom", traceback, None),),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )


def _setup_source(tmp_path: Path, content: str = "x = m.dict()\n") -> tuple[Path, Path]:
    source_root = tmp_path / "source"
    overlay_root = tmp_path / "overlay"
    source_root.mkdir()
    overlay_root.mkdir()
    (source_root / "app").mkdir()
    (source_root / "app" / "models.py").write_text(content)
    return source_root, overlay_root


def test_run_repo_raises_without_a_captured_baseline(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(baseline=None)
    sandbox = FakeSandbox(responses=[_passed_run()])
    try:
        run_repo(
            repo,
            image=sandbox.build(repo, "v1"),
            source_root=source_root,
            overlay_root=overlay_root,
            sandbox=sandbox,
            model_client=None,
            config=_config(),
        )
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "no captured baseline" in str(e)


def test_run_repo_scores_a_t1_only_full_green_run(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    sandbox = FakeSandbox(responses=[_passed_run()])

    result = run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=None,
        config=_config(),
        policy=SandboxPolicy(),
    )

    assert result.repo_id == "acme__widgets"
    assert result.pass_rate == 1.0
    assert result.full_green is True
    assert result.config.triage is True


def test_run_repo_rejects_a_t1_only_config_paired_with_a_real_model_client(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D62: config.tiers is the source of truth -- a mismatch against
    # the caller's own model_client must fail loud, not silently run repair() anyway.
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    sandbox = FakeSandbox(responses=[_passed_run()])
    config = EvalConfig(name="t1_only", model="fake", tiers=frozenset({"T1"}))

    try:
        run_repo(
            repo,
            image=sandbox.build(repo, "v1"),
            source_root=source_root,
            overlay_root=overlay_root,
            sandbox=sandbox,
            model_client=FakeModelClient(responses=[]),
            config=config,
        )
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "excludes T2/T3" in str(e)


def test_run_repo_t1_only_config_with_no_model_client_runs_fine(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    sandbox = FakeSandbox(responses=[_passed_run()])
    config = EvalConfig(name="t1_only", model="fake", tiers=frozenset({"T1"}))

    result = run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=None,
        config=config,
    )

    assert result.full_green is True


def test_run_repo_no_t1_config_leaves_the_overlay_unmodified_by_codemods(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D62: no_t1 threads enable_t1=False into build_migration_graph --
    # the file T1 would otherwise rewrite (x = m.dict()) must survive untouched.
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    sandbox = FakeSandbox(responses=[_passed_run()])
    config = EvalConfig(name="no_t1", model="fake", tiers=frozenset({"T2", "T3"}))

    run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=FakeModelClient(responses=[]),
        config=config,
    )

    assert (overlay_root / "app" / "models.py").read_text() == "x = m.dict()\n"


def test_run_repo_dumps_residual_failures_with_full_text_and_predicted_class(
    tmp_path: Path,
) -> None:
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    traceback = (
        "app/models.py:1: in <module>\n"
        "    from pydantic import BaseSettings\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    failing_run = TestRun(
        outcomes=(TestOutcome("t.py::test_a", "failed", 0.1, "boom", traceback, None),),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    sandbox = FakeSandbox(responses=[failing_run])
    failures_out = tmp_path / "failures.jsonl"

    run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=None,  # T1-only: no repair, finalizes after one red run
        config=_config(),
        failures_out=failures_out,
    )

    lines = failures_out.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["repo_id"] == "acme__widgets"
    assert record["node_id"] == "t.py::test_a"
    assert record["predicted_cls"] == "import_error"
    # full traceback+message text (triage.collect.collect_raw_failures' own format), not
    # Diagnosis.evidence's short, answer-revealing snippet
    assert record["text"] == f"{traceback}\nboom"


def test_run_repo_routes_repair_through_diagnosis_when_use_triage_is_true(
    tmp_path: Path,
) -> None:
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    traceback = "app/models.py:1: in <module>\nE   AssertionError: boom"
    sandbox = FakeSandbox(
        responses=[
            TestRun(
                outcomes=(TestOutcome("t.py::test_a", "failed", 0.1, "boom", traceback, None),),
                collection_errors=(),
                exit_code=1,
                duration_s=0.1,
                truncated=False,
            ),
            _passed_run(),
        ]
    )
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/models.py\n```python\nx = 2\n```\n",
                usd_cost=0.02,
                tokens_in=5,
                tokens_out=5,
            )
        ]
    )

    result = run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=fake_model,
        config=_config(triage=True),
    )

    assert len(fake_model.calls) == 1
    assert result.usd_spent == 0.02
    assert result.full_green is True


def test_build_retrieval_maps_graph_config_to_graph_retrieval() -> None:
    retrieval = _build_retrieval(_config(), repo_id="acme__widgets")
    assert isinstance(retrieval, GraphRetrieval)
    assert retrieval.repo_id == "acme__widgets"


def test_build_retrieval_maps_wholefile_config_to_wholefile_retrieval() -> None:
    config = EvalConfig(name="test", model="fake", retrieval="wholefile")
    retrieval = _build_retrieval(config, repo_id="acme__widgets")
    assert isinstance(retrieval, WholefileRetrieval)


def _run_git(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _make_clonable_repo(
    tmp_path: Path, content: str = "x = m.dict()\n", name: str = "origin"
) -> tuple[Path, str]:
    """A real, throwaway local git repo -- `run_corpus` calls `checkout_pre_sha`, which
    shells out to a real `git clone`. Cloning a local path involves no network at all
    (matches CLAUDE.md's "no network in unit tests" — this is disk + subprocess only),
    same real-local-git precedent tests/eval/test_diff_similarity_harness.py already
    establishes. `name` lets a test build several distinct origins under one tmp_path."""
    origin_dir = tmp_path / name
    origin_dir.mkdir()
    _run_git("git", "init", "-q", cwd=origin_dir)
    _run_git("git", "config", "user.email", "t@t.com", cwd=origin_dir)
    _run_git("git", "config", "user.name", "t", cwd=origin_dir)
    (origin_dir / "app").mkdir()
    (origin_dir / "app" / "models.py").write_text(content)
    _run_git("git", "add", ".", cwd=origin_dir)
    _run_git("git", "commit", "-q", "-m", "pre", cwd=origin_dir)
    sha = _run_git("git", "rev-parse", "HEAD", cwd=origin_dir)
    return origin_dir, sha


def test_run_corpus_with_resume_skips_a_cell_already_in_the_store(tmp_path: Path) -> None:
    config = _config()
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    # deliberately an invalid URL -- if the resume-skip logic didn't fire before
    # checkout_pre_sha, this repo would fail to clone and be silently dropped (caught by
    # run_corpus's own except Exception), which would ALSO make the assertion below fail,
    # just less informatively than a clean skip would.
    bad_repo = replace(repo, url="https://example.invalid/does/not/exist")

    source_root, overlay_root = _setup_source(tmp_path)
    store = ResultStore(tmp_path / "results.db")
    existing = run_repo(
        repo,
        image=ImageRef(
            tag="img",
            repo_id=repo.repo_id,
            sha=repo.pre_sha,
            pydantic="v2",
            deps_hash="x",
            test_cmd=repo.test_cmd,
        ),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=FakeSandbox(responses=[_passed_run()]),
        model_client=None,
        config=config,
    )
    store.save_result(existing, "deadbeef", written_at=1.0)
    resume = ResumeContext(store=store, corpus_sha="deadbeef")

    results = run_corpus(
        [bad_repo],
        work_root=tmp_path / "work",
        sandbox=FakeSandbox(responses=[_passed_run()]),
        model_client=None,
        config=config,
        resume=resume,
    )

    assert results == [existing]


def test_run_corpus_saves_a_fresh_result_and_a_second_call_skips_it(tmp_path: Path) -> None:
    origin_dir, pre_sha = _make_clonable_repo(tmp_path)
    repo = RepoSpec(
        repo_id="acme__widgets",
        url=str(origin_dir),
        pre_sha=pre_sha,
        post_sha=pre_sha,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
        baseline=_baseline(frozenset({"t.py::test_a"})),
    )
    config = _config()
    store = ResultStore(tmp_path / "results.db")
    resume = ResumeContext(store=store, corpus_sha="deadbeef")

    first = run_corpus(
        [repo],
        work_root=tmp_path / "work",
        sandbox=FakeSandbox(responses=[_passed_run()]),
        model_client=None,
        config=config,
        resume=resume,
    )
    assert len(first) == 1
    assert store.has_result(repo.repo_id, config_hash(config), "deadbeef") is True

    # a second call must NOT reach checkout_pre_sha again -- point url at a dead path so
    # a real re-clone attempt would raise, proving the skip (not a lucky re-clone) is why
    # this returns successfully.
    dead_repo = replace(repo, url="https://example.invalid/does/not/exist")
    second = run_corpus(
        [dead_repo],
        work_root=tmp_path / "work2",
        sandbox=FakeSandbox(responses=[_passed_run()]),
        model_client=None,
        config=config,
        resume=resume,
    )
    assert second == first


@dataclass
class _SlowFakeSandbox:
    """docs/decisions.md D66: proves run_corpus's ThreadPoolExecutor path is REAL
    concurrency, not just accepted parameters that still run sequentially. Looks up each
    repo's response by `image.repo_id` (read-only after construction, so safe without a
    lock) rather than FakeSandbox's shared `_index` counter above, which assumes one repo
    at a time and would race under real concurrent calls."""

    delay_s: float
    response: TestRun

    def build(self, repo, pydantic):  # type: ignore[no-untyped-def]
        return ImageRef(
            tag=f"{repo.repo_id}-{pydantic}",
            repo_id=repo.repo_id,
            sha=repo.pre_sha,
            pydantic=pydantic,
            deps_hash="x",
            test_cmd=repo.test_cmd,
        )

    def run_tests(self, image, workdir_overlay, policy, selection=None):  # type: ignore[no-untyped-def]
        time.sleep(self.delay_s)
        return self.response


def _clonable_repo_spec(tmp_path: Path, name: str) -> RepoSpec:
    origin_dir, pre_sha = _make_clonable_repo(tmp_path, name=name)
    return RepoSpec(
        repo_id=name,
        url=str(origin_dir),
        pre_sha=pre_sha,
        post_sha=pre_sha,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
        baseline=_baseline(frozenset({"t.py::test_a"})),
    )


def test_run_corpus_with_max_workers_runs_repos_concurrently_not_sequentially(
    tmp_path: Path,
) -> None:
    n_repos = 4
    delay_s = 0.3
    repos = [_clonable_repo_spec(tmp_path, f"repo{i}") for i in range(n_repos)]

    start = time.time()
    results = run_corpus(
        repos,
        work_root=tmp_path / "work",
        sandbox=_SlowFakeSandbox(delay_s=delay_s, response=_passed_run()),
        model_client=None,
        config=_config(),
        max_workers=n_repos,
    )
    elapsed = time.time() - start

    assert len(results) == n_repos
    # sequential would take >= n_repos * delay_s (1.2s); real concurrency should land
    # close to one delay_s plus git/scoring overhead. A generous bound (well under 2x one
    # delay) avoids flakiness while still failing hard if this silently ran sequentially.
    assert elapsed < delay_s * 2


def test_run_corpus_rejects_a_sub_one_max_workers(tmp_path: Path) -> None:
    try:
        run_corpus(
            [],
            work_root=tmp_path / "work",
            sandbox=FakeSandbox(responses=[]),
            model_client=None,
            config=_config(),
            max_workers=0,
        )
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_workers" in str(e)


def test_run_corpus_total_usd_cap_stops_starting_new_repos(tmp_path: Path) -> None:
    # sequential (max_workers=1) on purpose -- deterministic ordering makes this a clean
    # test of the budget-tracker LOGIC itself, independent of any real thread scheduling.
    repos = [_clonable_repo_spec(tmp_path, f"repo{i}") for i in range(3)]
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(text="", usd_cost=2.0, tokens_in=1, tokens_out=1) for _ in range(3)
        ]
    )
    # usd_cap_per_repo=1.0 guarantees exactly ONE repair() attempt per repo: the first
    # $2.0 spend already exceeds it (BudgetState.exceeded is usd_spent > usd_cap), so the
    # loop finalizes after one call -- without this, no_progress_threshold could let a
    # single repo consume more than one of the 3 scripted responses below, breaking this
    # test's "repo N spends exactly $2.0" assumption for reasons unrelated to the cap logic
    # actually being tested.
    config = EvalConfig(name="test", model="fake", usd_cap_per_repo=1.0)

    results = run_corpus(
        repos,
        work_root=tmp_path / "work",
        sandbox=FakeSandbox(responses=[_failed_run()]),
        model_client=fake_model,
        config=config,
        total_usd_cap=3.0,
    )

    # repo0 runs (spend now >= $2, still < $3 cap when repo1 is CHECKED) -- repo1 runs
    # (spend now >= $4) -- repo2 is skipped, since the cap is checked before it starts.
    assert len(results) == 2
