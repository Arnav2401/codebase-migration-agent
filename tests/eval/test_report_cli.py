import json
from collections import Counter
from dataclasses import replace
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


def _configs_dir(tmp_path: Path, *config_names: str) -> Path:
    """D77: the report only includes rows whose config_hash matches the CURRENT
    configs/<arm>.json, so a test that stores results must also declare the config those
    results were produced under."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(exist_ok=True)
    for name in config_names:
        cfg = EvalConfig(name=name, model="gemini-3.6-flash")
        (configs_dir / f"{name}.json").write_text(json.dumps(cfg.to_dict()))
    return configs_dir


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
            "--configs-dir",
            str(_configs_dir(tmp_path, "graph")),
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
            "--configs-dir",
            str(_configs_dir(tmp_path, "graph", "wholefile")),
        ],
    )

    content = out_path.read_text()
    assert "### graph" in content
    assert "### wholefile" in content


def test_report_excludes_rows_from_a_superseded_configuration(tmp_path: Path) -> None:
    """docs/decisions.md D77, found live: re-pointing an arm at a different model leaves
    the store holding two configurations under ONE arm name, and grouping by name alone
    would average across two different MODELS under a heading naming neither."""
    manifest_path = _manifest(tmp_path)
    c_sha = corpus_sha(manifest_path)
    results_db = tmp_path / "results.db"
    store = ResultStore(results_db)

    current = _result("acme__current")
    superseded = replace(
        current, repo_id="acme__superseded", config=replace(current.config, model="other-model")
    )
    store.save_result(current, c_sha, written_at=1.0)
    store.save_result(superseded, c_sha, written_at=2.0)
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
            "--configs-dir",
            str(_configs_dir(tmp_path, "graph")),
        ],
    )

    content = out_path.read_text()
    assert "acme__current" in content
    assert "acme__superseded" not in content
    assert "skipped 1 result(s) from superseded configurations" in result.output


def test_report_keeps_every_seed_of_the_current_configuration(tmp_path: Path) -> None:
    """docs/decisions.md D77, caught immediately after it landed: `seed` is part of
    `config_hash` (D63) so each seed resumes independently, but seeds are one configuration
    measured k times (D72), not k configurations. Matching on the full hash silently dropped
    seeds 1 and 2, making a k=3 sweep report as if it were k=1."""
    manifest_path = _manifest(tmp_path)
    c_sha = corpus_sha(manifest_path)
    results_db = tmp_path / "results.db"
    store = ResultStore(results_db)

    base = _result("acme__a")
    for seed in (0, 1, 2):
        seeded = replace(base, repo_id=f"acme__seed{seed}", config=replace(base.config, seed=seed))
        store.save_result(seeded, c_sha, written_at=float(seed))
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
            "--configs-dir",
            str(_configs_dir(tmp_path, "graph")),  # declares seed=0 only
        ],
    )

    content = out_path.read_text()
    for seed in (0, 1, 2):
        assert f"acme__seed{seed}" in content
    assert "skipped" not in result.output
