from collections import Counter
from pathlib import Path

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_main_report, write_results_table


def _config(seed: int = 0) -> EvalConfig:
    return EvalConfig(name="graph", model="gemini-3.6-flash", seed=seed)


def _result(
    repo_id: str,
    pass_rate: float,
    full_green: bool,
    usd_spent: float = 0.1,
    diff_line_jaccard: float | None = None,
    symbol_precision: float | None = None,
    symbol_recall: float | None = None,
    seed: int = 0,
) -> RepoResult:
    return RepoResult(
        repo_id=repo_id,
        config=_config(seed=seed),
        pass_rate=pass_rate,
        full_green=full_green,
        iterations=2,
        usd_spent=usd_spent,
        wallclock_s=1.0,
        final_diagnosis_counts=Counter(),
        avg_failures_per_diagnosis=0.0,
        scored_repairs=(),
        diff_line_jaccard=diff_line_jaccard,
        symbol_precision=symbol_precision,
        symbol_recall=symbol_recall,
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
    assert (
        "| no_t1 | 0 | no repos scored | no repos scored | — | "
        "no diff data | no diff data | no diff data |" in content
    )
    assert "### no_t1" in content


def test_write_results_table_renders_missing_diff_similarity_as_an_em_dash(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / "graph.md"
    write_results_table([_result("acme__a", 1.0, True)], out_path, config_name="graph")

    content = out_path.read_text()
    assert "| acme__a | 1.000 | True | 0.1000 | 2 | — | — | — |" in content
    assert "no diff data" in content  # summary line: zero repos had a measurement


def test_write_results_table_reports_diff_similarity_only_over_measured_repos(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / "graph.md"
    results = [
        _result(
            "acme__a", 1.0, True, diff_line_jaccard=0.5, symbol_precision=1.0, symbol_recall=0.5
        ),
        _result("acme__b", 0.0, False),  # not measured -- must not count as a 0.0
    ]

    write_results_table(results, out_path, config_name="graph")

    content = out_path.read_text()
    assert "| acme__a | 1.000 | True | 0.1000 | 2 | 0.500 | 1.000 | 0.500 |" in content
    assert "| acme__b | 0.000 | False | 0.1000 | 2 | — | — | — |" in content
    assert "(n=1/2)" in content  # only one of the two repos had a real measurement


def test_write_main_report_ci_bounds_bracket_the_point_estimate(tmp_path: Path) -> None:
    out_path = tmp_path / "main.md"
    results = [_result(f"acme__{i}", 0.1 * i, i > 5) for i in range(10)]
    write_main_report({"graph": results}, out_path)

    content = out_path.read_text()
    # the headline row's pass_rate mean is 0.450 -- confirm it actually appears with a
    # bracketed range next to it, not just a bare number.
    assert "0.450 [" in content


def test_write_results_table_aggregates_multiple_seeds_into_one_repo_row(
    tmp_path: Path,
) -> None:
    """docs/decisions.md D72 (eval/run.py --seeds): three seeds of the SAME repo must
    collapse into one row, not render as three separate repos."""
    out_path = tmp_path / "graph.md"
    results = [
        _result("acme__a", 1.0, True, seed=0),
        _result("acme__a", 0.5, False, seed=1),
        _result("acme__a", 1.0, True, seed=2),
    ]

    write_results_table(results, out_path, config_name="graph")

    content = out_path.read_text()
    assert "**1 repos (3 repo x seed runs)**" in content
    # mean of [1.0, 0.5, 1.0] = 0.833..., range [0.5, 1.0], k=3 seeds, 2/3 full green
    assert "0.833 [0.500, 1.000] (k=3 seeds)" in content
    assert "2/3" in content


def test_write_results_table_renders_a_single_seed_identically_to_before_d72(
    tmp_path: Path,
) -> None:
    """A repo with only one seed's RepoResult must render exactly as it did before
    seed-variance support existed -- no "(k=1 seeds)" or repo x seed notation anywhere."""
    out_path = tmp_path / "graph.md"
    write_results_table([_result("acme__a", 1.0, True)], out_path, config_name="graph")

    content = out_path.read_text()
    assert "| acme__a | 1.000 | True | 0.1000 | 2 | — | — | — |" in content
    assert "repo x seed" not in content
    assert "seeds)" not in content


def test_write_main_report_bootstraps_over_per_repo_seed_means_not_raw_rows(
    tmp_path: Path,
) -> None:
    """docs/decisions.md D72: an arm with one repo run under 3 seeds and one repo run
    under 1 seed has N=2 (repos), not N=4 (raw RepoResult rows) -- the bootstrap CI must
    resample repos, not repo x seed cells."""
    out_path = tmp_path / "main.md"
    results = [
        _result("acme__a", 1.0, True, seed=0),
        _result("acme__a", 1.0, True, seed=1),
        _result("acme__a", 1.0, True, seed=2),
        _result("acme__b", 0.0, False),
    ]

    write_main_report({"graph": results}, out_path)

    content = out_path.read_text()
    assert "| graph | 2 |" in content  # N=2 repos, not 4 raw rows
    # per-repo means are [1.0, 0.0] -> arm mean pass_rate 0.5, not (1+1+1+0)/4 = 0.75
    assert "0.500 [" in content
