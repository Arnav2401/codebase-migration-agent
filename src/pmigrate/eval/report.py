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
never actually rendered anywhere until D71). Per D57/D58, `None` on an individual
`RepoResult` means "not measured" (no human ground-truth diff, or neither side touched a
Python file), not a real 0.0 — rendered as `—` per repo, and excluded from the aggregate
mean/CI rather than counted as a zero, which would silently understate the metric.

docs/decisions.md D72: `eval/run.py --seeds` (phase-5-eval.md's k=3 seed-variance
protocol) can now score the SAME repo under the same named arm multiple times, once per
seed — each seed is its own independent `RepoResult` (`config.seed` differs, so
`config_hash` differs, so it's a genuinely separate resumable DB cell per D63). Both
functions below group by `repo_id` FIRST, then aggregate: `_repo_row` renders one table
row per repo, identical to the pre-seed-variance format when there's exactly one seed for
that repo, and a mean/range/count-across-seeds format when there's more than one. The
arm-level aggregate (mean pass_rate, full_green count, bootstrap CIs, diff-similarity
means) is likewise computed over PER-REPO means, not raw per-seed rows — so N stays "how
many repos this arm covers," not "how many repo x seed cells got scored," matching
phase-5-eval.md's "bootstrap CIs over repos."
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.stats import bootstrap_mean_ci

_DIFF_SIMILARITY_HEADER = "diff_line_jaccard | symbol_precision | symbol_recall"
# Phase 8's gate rides in the per-repo appendix, deliberately not the headline table
# (phase-8-optional.md: "Report it as an additional gate in the eval table, not as a
# headline") -- it answers "did this migration make the repo less safe", which is a
# different question from how well it migrated and must not dilute that number.
_SECURITY_HEADER = "security"


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _fmt_opt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _group_by_repo(results: Sequence[RepoResult]) -> dict[str, list[RepoResult]]:
    """One entry per distinct `repo_id`, preserving every `RepoResult` scored for it --
    length 1 unless `--seeds` (D72) ran more than one seed for this arm."""
    groups: dict[str, list[RepoResult]] = {}
    for r in results:
        groups.setdefault(r.repo_id, []).append(r)
    return groups


def _security_cell(seed_results: Sequence[RepoResult]) -> str:
    """`—` when the gate did not run, `clean` when it ran and found nothing introduced.
    Those must not render the same: a run that never scanned is not a clean scan (D99)."""
    measured = [r for r in seed_results if r.security_introduced is not None]
    if not measured:
        return "—"
    total = sum(r.security_introduced or 0 for r in measured)
    if total == 0:
        return "clean"
    worst = next(
        (
            sev
            for sev in ("HIGH", "MEDIUM", "LOW")
            if any(r.security_worst_severity == sev for r in measured)
        ),
        "?",
    )
    return f"**+{total} {worst.lower()}**"


def _diff_similarity_cells(seed_results: Sequence[RepoResult]) -> str:
    """Mean over whichever of this repo's seeds actually measured each metric (D57/D58:
    `None` means not measured, excluded rather than treated as 0.0). For a single-seed
    repo this reduces to exactly D71's original per-repo formatting -- a mean of one
    value is that value, and a mean of zero values is still `—`."""

    def cell(attr: str) -> str:
        values = [v for r in seed_results if (v := getattr(r, attr)) is not None]
        return "—" if not values else f"{_mean(values):.3f}"

    return f"{cell('diff_line_jaccard')} | {cell('symbol_precision')} | {cell('symbol_recall')}"


def _repo_row(repo_id: str, seed_results: Sequence[RepoResult]) -> str:
    """One markdown table row for `repo_id`. Renders identically to the pre-D72 format
    when `seed_results` has exactly one entry (every arm run before `--seeds` existed,
    and every single-seed run after it) -- `full_green` as a bare bool, `iterations` as a
    bare int, `pass_rate`/`usd_spent` as bare floats, no seed-count notation anywhere.
    Only renders the mean/range/count-across-seeds form once a repo genuinely has more
    than one seed's `RepoResult` to summarize."""
    diff_cells = _diff_similarity_cells(seed_results)
    sec_cell = _security_cell(seed_results)
    if len(seed_results) == 1:
        r = seed_results[0]
        return (
            f"| {repo_id} | {r.pass_rate:.3f} | {r.full_green} | "
            f"{r.usd_spent:.4f} | {r.iterations} | {diff_cells} | {sec_cell} |"
        )

    pass_rates = [r.pass_rate for r in seed_results]
    full_green_count = sum(1 for r in seed_results if r.full_green)
    total_usd = sum(r.usd_spent for r in seed_results)
    mean_iterations = _mean([float(r.iterations) for r in seed_results])
    k = len(seed_results)
    pass_rate_cell = (
        f"{_mean(pass_rates):.3f} [{min(pass_rates):.3f}, {max(pass_rates):.3f}] (k={k} seeds)"
    )
    return (
        f"| {repo_id} | {pass_rate_cell} | {full_green_count}/{k} | "
        f"{total_usd:.4f} | {mean_iterations:.1f} | {diff_cells} | {sec_cell} |"
    )


def _per_repo_means(groups: dict[str, list[RepoResult]], attr: str) -> list[float]:
    """One value per repo -- the mean of `attr` (`pass_rate` or `full_green`, the latter
    coerced to 0.0/1.0) across whichever seeds scored that repo. Feeding THESE into
    `bootstrap_mean_ci`, rather than one entry per raw `RepoResult`, keeps N equal to the
    repo count even when some repos ran under multiple seeds (D72) — the bootstrap
    resamples repos, not repo x seed cells (phase-5-eval.md: "bootstrap 95% CIs over
    repos")."""
    return [
        _mean([float(getattr(r, attr)) for r in seed_results]) for seed_results in groups.values()
    ]


def _per_repo_diff_means(groups: dict[str, list[RepoResult]], attr: str) -> list[float]:
    """Like `_per_repo_means`, but for an Optional diff-similarity attr: a repo
    contributes its own mean only over the seeds that actually measured it, and
    contributes nothing at all if none of its seeds did (D57/D58's "not measured" stays
    excluded, never a fabricated 0.0)."""
    means = []
    for seed_results in groups.values():
        values = [v for r in seed_results if (v := getattr(r, attr)) is not None]
        if values:
            means.append(_mean(values))
    return means


def _diff_ci_or_missing(per_repo_means: list[float], total_repos: int) -> str:
    if not per_repo_means:
        return "no diff data"
    ci = bootstrap_mean_ci(per_repo_means)
    return (
        f"{ci.point_estimate:.3f} [{ci.ci_low:.3f}, {ci.ci_high:.3f}] "
        f"(n={len(per_repo_means)}/{total_repos})"
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

    groups = _group_by_repo(results)
    full_green_count = sum(1 for g in groups.values() if all(r.full_green for r in g))
    mean_pass_rate = _mean(_per_repo_means(groups, "pass_rate"))
    total_usd = sum(r.usd_spent for r in results)

    repo_count_note = f" ({len(results)} repo x seed runs)" if len(results) != len(groups) else ""
    lines.append(
        f"**{len(groups)} repos{repo_count_note}** — {full_green_count} full green "
        f"(every seed passed), mean pass rate {mean_pass_rate:.3f}, total cost ${total_usd:.2f}"
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
        f"{_diff_ci_or_missing(_per_repo_diff_means(groups, 'diff_line_jaccard'), len(groups))} "
        "line jaccard, "
        f"{_diff_ci_or_missing(_per_repo_diff_means(groups, 'symbol_precision'), len(groups))} "
        "symbol precision, "
        f"{_diff_ci_or_missing(_per_repo_diff_means(groups, 'symbol_recall'), len(groups))} "
        "symbol recall. `—` per repo below means not measured (no human ground-truth "
        "diff, or neither side touched a Python file), not a real 0.0."
    )
    lines.append("")
    lines.append(
        f"| repo_id | pass_rate | full_green | usd_spent | iterations | "
        f"{_DIFF_SIMILARITY_HEADER} | {_SECURITY_HEADER} |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for repo_id in sorted(groups):
        lines.append(_repo_row(repo_id, groups[repo_id]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def _model_split_caveat(results_by_config: dict[str, list[RepoResult]]) -> list[str]:
    """Emitted ONLY when the arms in one report don't all run the same model -- silent
    otherwise, so a single-model report carries no noise.

    Exists because the headline table's whole value is that two rows differ in exactly one
    thing, so the row-to-row delta names what that thing cost. The moment arms span models
    that stops being true: `no_t1_groq` vs `no_t1` differs in BOTH the tier set and the
    model, so the delta between them measures neither one. Reading it as "removing T1 did
    this" is precisely the kind of dishonest number CLAUDE.md's review rules exist to
    catch, and nothing else in this report would stop a reader from doing it -- the arm
    NAME says `no_t1`, and the model it ran under is invisible in the row.

    Derived from each `RepoResult`'s own `config.model` rather than a hardcoded list of
    which arms are "the Groq ones": the arms in this repo change, and a hand-maintained
    list would silently go stale the first time someone adds an arm without updating it.
    """
    models_by_arm: dict[str, set[str]] = {}
    for name, results in results_by_config.items():
        models = {r.config.model for r in results}
        if models:  # an arm with no scored repos has no model to report
            models_by_arm[name] = models

    distinct_models = set().union(*models_by_arm.values()) if models_by_arm else set()
    if len(distinct_models) <= 1:
        return []

    lines = [
        "",
        "> **These arms do not all run the same model — do not read across the split.** "
        "Each row differs from the others in more than the thing its name calls out, so a "
        "difference between two arms on opposite sides of the split confounds the "
        "ablation with the model change and measures neither. Compare only within a model:",
        ">",
    ]
    for model in sorted(distinct_models):
        arms = sorted(name for name, models in models_by_arm.items() if model in models)
        lines.append(f"> - `{model}`: {', '.join(f'`{a}`' for a in arms)}")
    lines.append(">")
    lines.append(
        "> Why an arm runs the model it does varies, and this warning deliberately does "
        "NOT guess: an arm may name a second provider because comparing providers IS its "
        "ablation, or because the first one was rate-limited and the arm was re-run "
        "elsewhere to be measurable at all. Both produce the same table and the same "
        "hazard above."
    )
    lines.append(">")
    lines.append(
        "> Separately, and load-bearing for reading ANY row here: Gemini's free tier on "
        "this project is 20 requests/day and trickle-refills rather than resetting cleanly "
        "(docs/decisions.md D48), so an arm can score every one of its cells while every "
        "single repair call returns 429. Such an arm reports real test outcomes but no "
        "real repair activity — its numbers are T1's deterministic codemod alone, not the "
        "tier or retrieval strategy its name describes. The tell is the cost column: a "
        "near-zero spend next to a full N means nothing was actually repaired, and that "
        "row is measuring T1, whatever its name says."
    )
    return lines


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
        "that width is reported here rather than hidden. N is the number of distinct "
        "repos, not repo x seed cells, even for an arm run under multiple seeds "
        "(docs/decisions.md D72)."
    )
    lines.extend(_model_split_caveat(results_by_config))
    lines.append("")
    lines.append(
        "| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | "
        "line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | "
        "symbol_recall (mean [95% CI], n measured) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")

    for name in sorted(results_by_config):
        results = results_by_config[name]
        if not results:
            lines.append(
                f"| {name} | 0 | no repos scored | no repos scored | — | "
                "no diff data | no diff data | no diff data |"
            )
            continue

        groups = _group_by_repo(results)
        pass_rate_ci = bootstrap_mean_ci(_per_repo_means(groups, "pass_rate"))
        full_green_ci = bootstrap_mean_ci(_per_repo_means(groups, "full_green"))
        mean_cost = sum(r.usd_spent for r in results) / len(groups)
        n = len(groups)
        jaccard_ci = _diff_ci_or_missing(_per_repo_diff_means(groups, "diff_line_jaccard"), n)
        precision_ci = _diff_ci_or_missing(_per_repo_diff_means(groups, "symbol_precision"), n)
        recall_ci = _diff_ci_or_missing(_per_repo_diff_means(groups, "symbol_recall"), n)

        lines.append(
            f"| {name} | {n} | "
            f"{pass_rate_ci.point_estimate:.3f} [{pass_rate_ci.ci_low:.3f}, "
            f"{pass_rate_ci.ci_high:.3f}] | "
            f"{full_green_ci.point_estimate:.3f} [{full_green_ci.ci_low:.3f}, "
            f"{full_green_ci.ci_high:.3f}] | "
            f"${mean_cost:.2f} | {jaccard_ci} | {precision_ci} | {recall_ci} |"
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
        groups = _group_by_repo(results)
        header = "| repo_id | pass_rate | full_green | usd_spent | iterations | "
        lines.append(f"{header}{_DIFF_SIMILARITY_HEADER} | {_SECURITY_HEADER} |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for repo_id in sorted(groups):
            lines.append(_repo_row(repo_id, groups[repo_id]))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
