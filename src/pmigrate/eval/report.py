"""Phase 5's results tables. `write_results_table` (docs/decisions.md D64) writes one
arm's own per-repo table plus a plain mean/count aggregate — deliberately no bootstrap CI
there, since phase-5-eval.md scopes CIs specifically to `docs/results/main.md`'s cross-arm
headline table ("bootstrap 95% CIs over repos... state it"), not to a single arm's own
report. A per-repo table with an unweighted mean is still an honest artifact on its own:
phase-5-eval.md's own words are "publish the full per-repo table so nobody has to trust
the aggregate," which `write_results_table` satisfies without needing a CI to back it.

`write_main_report` (docs/decisions.md D65) is that combining step: one headline row per
arm (mean pass_rate and full_green fraction, each with a bootstrap 95% CI from
`eval/stats.py`) plus every arm's own per-repo appendix underneath.

Both tables also carry the three diff-similarity metrics (`diff_line_jaccard`,
`symbol_precision`, `symbol_recall` — docs/phase-5-eval.md's "report both" requirement,
computed by `eval/diff_similarity.py`, wired into `RepoResult` by `eval/harness.py`, but
never actually rendered anywhere until now). Per D57/D58, `None` on an individual
`RepoResult` means "not measured" (no human ground-truth diff, or neither side touched a
Python file), not a real 0.0 — rendered as `—` per repo, and excluded from the aggregate
mean/CI rather than counted as a zero, which would silently understate the metric.
`_diff_ci_or_missing` reports how many repos actually had a measurement (`n=k/N`) so a
mean over a handful of repos isn't mistaken for one over the whole arm; an arm with zero
measured repos gets an explicit "no diff data" instead of `bootstrap_mean_ci`'s
empty-input `ValueError`.
"""

from __future__ import annotations

from pathlib import Path

from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.stats import bootstrap_mean_ci

_DIFF_SIMILARITY_HEADER = "diff_line_jaccard | symbol_precision | symbol_recall"


def _fmt_opt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _diff_similarity_cells(r: RepoResult) -> str:
    jaccard = _fmt_opt(r.diff_line_jaccard)
    precision = _fmt_opt(r.symbol_precision)
    recall = _fmt_opt(r.symbol_recall)
    return f"{jaccard} | {precision} | {recall}"


def _diff_ci_or_missing(results: list[RepoResult], attr: str) -> str:
    values = [v for r in results if (v := getattr(r, attr)) is not None]
    if not values:
        return "no diff data"
    ci = bootstrap_mean_ci(values)
    return (
        f"{ci.point_estimate:.3f} [{ci.ci_low:.3f}, {ci.ci_high:.3f}] "
        f"(n={len(values)}/{len(results)})"
    )


def write_results_table(results: list[RepoResult], out_path: Path, *, config_name: str) -> None:
    """`results` may be empty (every repo in the split failed to clone/build, or the split
    has zero repos) -- writes a table header plus "no repos scored" rather than crashing on
    an empty mean, since a silent empty file would look like a bug, not a real outcome."""
    lines = [f"# Eval results — `{config_name}`", ""]

    if not results:
        lines.append("No repos scored.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines) + "\n")
        return

    full_green_count = sum(1 for r in results if r.full_green)
    mean_pass_rate = sum(r.pass_rate for r in results) / len(results)
    total_usd = sum(r.usd_spent for r in results)

    lines.append(
        f"**{len(results)} repos** — {full_green_count} full green, "
        f"mean pass rate {mean_pass_rate:.3f}, total cost ${total_usd:.2f}"
    )
    lines.append("")
    lines.append(
        "No confidence interval below — this table reports one arm in isolation. "
        "Bootstrap 95% CIs are computed when combining arms into `main.md` "
        "(`write_main_report`, a separate step over every arm's own repos)."
    )
    lines.append("")
    lines.append(
        "Diff-similarity (docs/phase-5-eval.md): "
        f"{_diff_ci_or_missing(results, 'diff_line_jaccard')} line jaccard, "
        f"{_diff_ci_or_missing(results, 'symbol_precision')} symbol precision, "
        f"{_diff_ci_or_missing(results, 'symbol_recall')} symbol recall. "
        "`—` per repo below means not measured (no human ground-truth diff, or neither "
        "side touched a Python file), not a real 0.0."
    )
    lines.append("")
    lines.append(
        f"| repo_id | pass_rate | full_green | usd_spent | iterations | {_DIFF_SIMILARITY_HEADER} |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: r.repo_id):
        lines.append(
            f"| {r.repo_id} | {r.pass_rate:.3f} | {r.full_green} | "
            f"{r.usd_spent:.4f} | {r.iterations} | {_diff_similarity_cells(r)} |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def write_main_report(results_by_config: dict[str, list[RepoResult]], out_path: Path) -> None:
    """One headline row per arm plus every arm's own per-repo appendix underneath.
    `results_by_config` maps an arm's `EvalConfig.name` to every `RepoResult` scored under
    it -- an arm with an empty list is reported as "no repos scored" rather than crashing
    on `bootstrap_mean_ci`'s empty-input check, matching `write_results_table`'s own
    empty-results handling."""
    lines = ["# Eval results — main", ""]

    if not results_by_config:
        lines.append("No results yet.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines) + "\n")
        return

    lines.append(
        "Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling "
        "REPOS within each arm — not a normal-approximation interval, since a few dozen "
        "repos is a small, plausibly non-normal sample. A narrow N means a wide interval; "
        "that width is reported here rather than hidden."
    )
    lines.append("")
    lines.append(
        "| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | "
        "line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | "
        "symbol_recall (mean [95% CI], n measured) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")

    for name in sorted(results_by_config):
        results = results_by_config[name]
        if not results:
            lines.append(
                f"| {name} | 0 | no repos scored | no repos scored | — | "
                "no diff data | no diff data | no diff data |"
            )
            continue

        pass_rate_ci = bootstrap_mean_ci([r.pass_rate for r in results])
        full_green_ci = bootstrap_mean_ci([float(r.full_green) for r in results])
        mean_cost = sum(r.usd_spent for r in results) / len(results)

        lines.append(
            f"| {name} | {len(results)} | "
            f"{pass_rate_ci.point_estimate:.3f} [{pass_rate_ci.ci_low:.3f}, "
            f"{pass_rate_ci.ci_high:.3f}] | "
            f"{full_green_ci.point_estimate:.3f} [{full_green_ci.ci_low:.3f}, "
            f"{full_green_ci.ci_high:.3f}] | "
            f"${mean_cost:.2f} | "
            f"{_diff_ci_or_missing(results, 'diff_line_jaccard')} | "
            f"{_diff_ci_or_missing(results, 'symbol_precision')} | "
            f"{_diff_ci_or_missing(results, 'symbol_recall')} |"
        )

    lines.append("")
    lines.append("## Per-repo appendix")

    for name in sorted(results_by_config):
        results = results_by_config[name]
        lines.append("")
        lines.append(f"### {name}")
        lines.append("")
        if not results:
            lines.append("No repos scored.")
            continue
        header = "| repo_id | pass_rate | full_green | usd_spent | iterations | "
        lines.append(f"{header}{_DIFF_SIMILARITY_HEADER} |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for r in sorted(results, key=lambda r: r.repo_id):
            lines.append(
                f"| {r.repo_id} | {r.pass_rate:.3f} | {r.full_green} | "
                f"{r.usd_spent:.4f} | {r.iterations} | {_diff_similarity_cells(r)} |"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
