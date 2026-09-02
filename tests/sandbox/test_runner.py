import subprocess
from pathlib import Path

import pmigrate.sandbox.runner as runner_mod
from pmigrate.sandbox.runner import DockerSandbox
from pmigrate.types import ImageRef, SandboxPolicy


def _image_ref() -> ImageRef:
    return ImageRef(
        tag="pmigrate-sandbox:test",
        repo_id="acme__widgets",
        sha="a" * 40,
        pydantic="v2",
        deps_hash="abc123",
        test_cmd=("pytest", "-q"),
    )


def test_timeout_force_kills_container_and_reports_timeout(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Verified against a live Docker daemon (docs/decisions.md D13): killing the `docker
    # run` CLI process on a Python-level timeout does NOT stop the container itself — it
    # keeps running orphaned. The fix is an explicit `docker kill <name>` in the timeout
    # handler; this test proves that second call actually happens, by name.
    calls = []

    def fake_run(args, capture_output, timeout):  # type: ignore[no-untyped-def]
        calls.append(args)
        if args[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)
        return None  # the docker kill call succeeds

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy(timeout_s=5))

    assert run.outcomes == ()
    assert run.exit_code == -1
    assert "timed out after 5s" in run.collection_errors[0]
    assert "force-killed" in run.collection_errors[0]

    assert len(calls) == 2
    run_args, kill_args = calls
    assert kill_args[:2] == ["docker", "kill"]
    name_flag_idx = run_args.index("--name")
    assert kill_args[2] == run_args[name_flag_idx + 1]  # killed the SAME container it started


def test_timeout_where_kill_itself_times_out_is_reported(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run(args, capture_output, timeout):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy(timeout_s=5))

    assert "also timed out" in run.collection_errors[0]


def test_missing_report_file_produces_crashed_result(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # subprocess "succeeds" (e.g. container was OOM-killed after producing no output) but
    # never writes report.json — must not be silently read as zero failures.
    completed = subprocess.CompletedProcess(args=[], returncode=137, stdout=b"", stderr=b"")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy())

    assert run.outcomes == ()
    assert run.exit_code == -1
    assert "no json report produced" in run.collection_errors[0]
    assert "exit code 137" in run.collection_errors[0]


def test_missing_report_file_surfaces_real_stderr(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # docs/decisions.md D43: a fatal conftest.py import error aborts the whole pytest
    # session before json-report can write anything — the actual, legible pytest error
    # was always in stderr; it just wasn't being read.
    stderr = (
        b"ImportError while loading conftest '/repo/tests/conftest.py'.\nE   AttributeError: boom"
    )
    completed = subprocess.CompletedProcess(args=[], returncode=4, stdout=b"", stderr=stderr)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy())

    assert "ImportError while loading conftest" in run.collection_errors[0]
    assert "AttributeError: boom" in run.collection_errors[0]


def test_malformed_json_report_produces_crashed_result(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def fake_run(args, capture_output, timeout):  # type: ignore[no-untyped-def]
        # find the -v host_dir:/out mount and write garbage where report.json should go
        idx = args.index("-v")  # workdir_overlay=None, so this is the output mount
        host_dir = Path(args[idx + 1].split(":")[0])
        (host_dir / runner_mod.REPORT_FILENAME).write_text("{not valid json")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy())

    assert run.outcomes == ()
    assert "malformed" in run.collection_errors[0]


def test_valid_report_is_parsed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run(args, capture_output, timeout):  # type: ignore[no-untyped-def]
        idx = args.index("-v")
        host_dir = Path(args[idx + 1].split(":")[0])
        (host_dir / runner_mod.REPORT_FILENAME).write_text(
            '{"duration": 0.1, "exitcode": 0, "tests": ['
            '{"nodeid": "t.py::ok", "outcome": "passed", '
            '"call": {"duration": 0.1, "outcome": "passed"}}], "collectors": []}'
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = DockerSandbox()
    run = sandbox.run_tests(_image_ref(), None, SandboxPolicy())

    assert len(run.outcomes) == 1
    assert run.outcomes[0].node_id == "t.py::ok"
    assert run.outcomes[0].status == "passed"


def test_selection_and_continue_on_collection_errors_always_present(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured_args = {}

    def fake_run(args, capture_output, timeout):  # type: ignore[no-untyped-def]
        captured_args["args"] = args
        return subprocess.CompletedProcess(args=args, returncode=1, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sandbox = DockerSandbox()
    sandbox.run_tests(
        _image_ref(), None, SandboxPolicy(), selection=["t.py::test_a", "t.py::test_b"]
    )

    args = captured_args["args"]
    assert "--continue-on-collection-errors" in args
    assert "t.py::test_a" in args and "t.py::test_b" in args
    assert "-p" in args and "no:randomly" in args


def test_docker_sandbox_build_delegates_to_image_module(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    called = {}
    monkeypatch.setattr(
        runner_mod,
        "build_image",
        lambda repo, pydantic: called.setdefault("args", (repo, pydantic)),
    )
    from pmigrate.types import RepoSpec

    spec = RepoSpec(
        repo_id="x",
        url="https://example.invalid",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest",),
    )
    DockerSandbox().build(spec, "v2")
    assert called["args"] == (spec, "v2")
