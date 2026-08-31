from pathlib import Path

from pmigrate.corpus.manifest_io import load_manifest, save_manifest
from pmigrate.types import BaselineResult, DiffStats, RepoSpec


def _sample_spec() -> RepoSpec:
    return RepoSpec(
        repo_id="acme__widgets",
        url="https://github.com/acme/widgets",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "-e", ".[test]"),
        test_cmd=("pytest", "-q"),
        setup_overrides=("RUN apt-get update",),
        split="dev",
        baseline=BaselineResult(
            passed=frozenset({"tests/test_a.py::test_one"}),
            failed=frozenset(),
            skipped=frozenset({"tests/test_a.py::test_skipped"}),
            flaky=frozenset(),
            duration_s=12.3,
        ),
        human_diff_stats=DiffStats(
            files_changed=3,
            lines_added=40,
            lines_removed=20,
            changed_paths=("requirements.txt", "widgets/models.py", "widgets/settings.py"),
        ),
    )


def test_round_trip(tmp_path: Path) -> None:
    spec = _sample_spec()
    path = tmp_path / "manifest.json"
    save_manifest([spec], path)
    loaded = load_manifest(path)
    assert loaded == [spec]


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "nope.json") == []


def test_round_trip_without_baseline(tmp_path: Path) -> None:
    spec = RepoSpec(
        repo_id="x__y",
        url="https://github.com/x/y",
        pre_sha="c" * 40,
        post_sha="d" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "-e", "."),
        test_cmd=("pytest",),
    )
    path = tmp_path / "manifest.json"
    save_manifest([spec], path)
    assert load_manifest(path) == [spec]
