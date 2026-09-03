"""Phase 5's per-arm results table (docs/decisions.md D64, phase-5-eval.md's "writes
docs/results/*.md" deliverable). Deliberately minimal: the full per-repo table plus a
mean/count aggregate, no bootstrap CI. phase-5-eval.md scopes CIs specifically to
`docs/results/main.md`'s cross-arm headline table ("bootstrap 95% CIs over repos... state
it"), not to a single arm's own report -- that combining-and-CI step is separate, later
work, tracked on its own. A per-repo table with an unweighted mean is still an honest
artifact on its own: phase-5-eval.md's own words are "publish the full per-repo table so
nobody has to trust the aggregate," which this satisfies without needing a CI to back it.
"""

from __future__ import annotations

from pathlib import Path

from pmigrate.eval.metrics import RepoResult


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
        "Bootstrap 95% CIs are computed once when combining arms into `main.md` "
        "(a separate, later step)."
    )
    lines.append("")
    lines.append("| repo_id | pass_rate | full_green | usd_spent | iterations |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: r.repo_id):
        lines.append(
            f"| {r.repo_id} | {r.pass_rate:.3f} | {r.full_green} | "
            f"{r.usd_spent:.4f} | {r.iterations} |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
