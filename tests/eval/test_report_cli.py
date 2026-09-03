from collections import Counter
from pathlib import Path

import typer
from typer.testing import CliRunner

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report_cli import main
from pmigrate.eval.store import ResultStore, corpus_sha

runner = CliRunner()
app = typer.Typer()
app.command()(main)


def _manifest(tmp_path: Path, content: str = '[{"repo_id": "a"}]') -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(content)
    return manifest_path


def _result(repo_id: str, config_name: str = "graph") -> RepoResult:
    return RepoResult(
        repo_id=repo_id,
        config=EvalConfig(name=config_name, model="gemini-3.6-flash"),
        pass_rate=1.0,
        full_green=True,
        iterations=1,
        usd_spent=0.0,
        wallclock_s=1.0,
        final_diagnosis_counts=Counter(),
        avg_failures_per_diagnosis=0.0,
        scored_repairs=(),
    )


def test_report_writes_main_md_from_stored_results(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    c_sha = corpus_sha(manifest_path)
    results_db = tmp_path / "results.db"
    store = ResultStore(results_db)
    store.save_result(_result("acme__a"), c_sha, written_at=1.0)
    store.close()

    out_path = tmp_path / "main.md"
    result = runner.invoke(
        app,
        [
            "--results-db",
            str(results_db),
            "--manifest-path",
            str(manifest_path),
            "--out-path",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert "acme__a" in out_path.read_text()


def test_report_scopes_to_the_current_manifests_corpus_sha(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    results_db = tmp_path / "results.db"
    store = ResultStore(results_db)
    store.save_result(_result("acme__stale"), "some-other-corpus-sha", written_at=1.0)
    store.close()

    out_path = tmp_path / "main.md"
    result = runner.invoke(
        app,
        [
            "--results-db",
            str(results_db),
            "--manifest-path",
            str(manifest_path),
            "--out-path",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    assert "No results yet." in out_path.read_text()
    assert "acme__stale" not in out_path.read_text()


def test_report_groups_results_by_config_name(tmp_path: Path) -> None:
    manifest_path = _manifest(tmp_path)
    c_sha = corpus_sha(manifest_path)
    results_db = tmp_path / "results.db"
    store = ResultStore(results_db)
    store.save_result(_result("acme__a", config_name="graph"), c_sha, written_at=1.0)
    store.save_result(_result("acme__b", config_name="wholefile"), c_sha, written_at=2.0)
    store.close()

    out_path = tmp_path / "main.md"
    runner.invoke(
        app,
        [
            "--results-db",
            str(results_db),
            "--manifest-path",
            str(manifest_path),
            "--out-path",
            str(out_path),
        ],
    )

    content = out_path.read_text()
    assert "### graph" in content
    assert "### wholefile" in content
