from collections import Counter
from pathlib import Path

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_results_table


def _config() -> EvalConfig:
    return EvalConfig(name="graph", model="gemini-3.6-flash")


def _result(repo_id: str, pass_rate: float, full_green: bool, usd_spent: float = 0.1) -> RepoResult:
    return RepoResult(
        repo_id=repo_id,
        config=_config(),
        pass_rate=pass_rate,
        full_green=full_green,
        iterations=2,
        usd_spent=usd_spent,
        wallclock_s=1.0,
        final_diagnosis_counts=Counter(),
        avg_failures_per_diagnosis=0.0,
        scored_repairs=(),
    )


def test_write_results_table_reports_no_repos_scored_for_an_empty_list(tmp_path: Path) -> None:
    out_path = tmp_path / "graph.md"
    write_results_table([], out_path, config_name="graph")

    content = out_path.read_text()
    assert "No repos scored." in content


def test_write_results_table_includes_every_repo_and_an_aggregate(tmp_path: Path) -> None:
    out_path = tmp_path / "graph.md"
    results = [
        _result("acme__a", 1.0, True, usd_spent=0.5),
        _result("acme__b", 0.5, False, usd_spent=1.5),
    ]

    write_results_table(results, out_path, config_name="graph")

    content = out_path.read_text()
    assert "acme__a" in content
    assert "acme__b" in content
    assert "2 repos" in content
    assert "1 full green" in content
    assert "$2.00" in content  # total cost, 0.5 + 1.5


def test_write_results_table_names_the_config_in_the_heading(tmp_path: Path) -> None:
    out_path = tmp_path / "graph.md"
    write_results_table([], out_path, config_name="wholefile")

    assert "`wholefile`" in out_path.read_text()


def test_write_results_table_does_not_claim_a_confidence_interval(tmp_path: Path) -> None:
    out_path = tmp_path / "graph.md"
    write_results_table([_result("acme__a", 1.0, True)], out_path, config_name="graph")

    content = out_path.read_text().lower()
    assert "ci" not in content.split()  # no stray "CI" token pretending one was computed
    assert "confidence interval" in content
