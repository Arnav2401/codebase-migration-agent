from collections import Counter
from pathlib import Path

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_main_report, write_results_table


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


def test_write_main_report_reports_no_results_for_an_empty_dict(tmp_path: Path) -> None:
    out_path = tmp_path / "main.md"
    write_main_report({}, out_path)

    assert "No results yet." in out_path.read_text()


def test_write_main_report_includes_a_headline_row_per_arm(tmp_path: Path) -> None:
    out_path = tmp_path / "main.md"
    results_by_config = {
        "graph": [_result("acme__a", 1.0, True), _result("acme__b", 0.5, False)],
        "wholefile": [_result("acme__a", 0.2, False)],
    }

    write_main_report(results_by_config, out_path)

    content = out_path.read_text()
    assert "| graph | 2 |" in content
    assert "| wholefile | 1 |" in content
    assert "### graph" in content
    assert "### wholefile" in content
    assert "acme__a" in content
    assert "acme__b" in content


def test_write_main_report_reports_an_empty_arm_without_crashing(tmp_path: Path) -> None:
    out_path = tmp_path / "main.md"
    write_main_report({"graph": [_result("acme__a", 1.0, True)], "no_t1": []}, out_path)

    content = out_path.read_text()
    assert "| no_t1 | 0 | no repos scored | no repos scored | — |" in content
    assert "### no_t1" in content


def test_write_main_report_ci_bounds_bracket_the_point_estimate(tmp_path: Path) -> None:
    out_path = tmp_path / "main.md"
    results = [_result(f"acme__{i}", 0.1 * i, i > 5) for i in range(10)]
    write_main_report({"graph": results}, out_path)

    content = out_path.read_text()
    # the headline row's pass_rate mean is 0.450 -- confirm it actually appears with a
    # bracketed range next to it, not just a bare number.
    assert "0.450 [" in content
