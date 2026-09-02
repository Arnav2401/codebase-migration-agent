import json
from dataclasses import dataclass, field
from pathlib import Path

from pmigrate.agent.model_client import FakeModelClient, ModelResponse
from pmigrate.eval.harness import run_repo
from pmigrate.types import (
    BaselineResult,
    ImageRef,
    RepoSpec,
    SandboxPolicy,
    TestOutcome,
    TestRun,
)


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
        )
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "no captured baseline" in str(e)


def test_run_repo_scores_a_t1_only_full_green_run(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    repo = _repo(_baseline(frozenset({"t.py::test_a"})))
    sandbox = FakeSandbox(responses=[_passed_run()])

    score = run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=None,
        policy=SandboxPolicy(),
    )

    assert score.repo_id == "acme__widgets"
    assert score.pass_rate == 1.0
    assert score.full_green is True
    assert score.use_triage is True


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

    score = run_repo(
        repo,
        image=sandbox.build(repo, "v1"),
        source_root=source_root,
        overlay_root=overlay_root,
        sandbox=sandbox,
        model_client=fake_model,
        use_triage=True,
    )

    assert len(fake_model.calls) == 1
    assert score.usd_spent == 0.02
    assert score.full_green is True
