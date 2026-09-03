"""Phase 5's bootstrap confidence intervals (docs/decisions.md D65, phase-5-eval.md's
"Statistics — bootstrap 95% CIs over repos" line). Pure, no I/O -- `eval/report.py`'s
`write_main_report` is the only caller, kept separate so the resampling logic is
independently testable without writing a single markdown file.

Percentile bootstrap (resample WITH replacement, take the empirical percentiles of the
resampled means) rather than a normal-approximation interval -- the standard
nonparametric choice for a small (N in the tens), plausibly non-normal sample of per-repo
scores, which is exactly phase-5-eval.md's own stated situation ("With N≈34 the interval
is roughly ±15 points"). Plain `random.Random`, not numpy -- this project already avoids
numpy where a for-loop is fine (`agent/retrieval.py`'s `_cosine_similarity`), and a few
thousand resamples over a few dozen values has no real performance case for it.

The resampling seed is fixed and INDEPENDENT of `EvalConfig.seed` -- the latter seeds one
migration run's own LLM sampling; this seeds the STATISTICS computed after the fact, over
already-fixed data. Both need to be fixed for the same reason (I6: runs reproducible), but
conflating them would make a re-run's CI move with the agent config a stats question has
no business depending on.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapResult:
    point_estimate: float
    ci_low: float
    ci_high: float
    n: int  # repos the estimate was computed over, not the resample count


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    n_resamples: int = 10000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapResult:
    """`values` is one number per repo (e.g. each repo's pass_rate, or 0.0/1.0 for
    full_green) -- the bootstrap resamples REPOS, matching phase-5-eval.md's "bootstrap
    95% CIs over repos," not resampling within a single repo's own internal test count."""
    if not values:
        raise ValueError("bootstrap_mean_ci needs at least one value")

    n = len(values)
    point_estimate = sum(values) / n

    if n == 1:
        # one repo has no resampling variance to speak of -- a resample of a single value
        # is that same value every time, so an interval collapsed to the point estimate is
        # the honest answer, not an artificially wide or narrow computed one.
        return BootstrapResult(
            point_estimate=point_estimate, ci_low=point_estimate, ci_high=point_estimate, n=n
        )

    rng = random.Random(seed)
    resampled_means = []
    for _ in range(n_resamples):
        resample_sum = sum(values[rng.randrange(n)] for _ in range(n))
        resampled_means.append(resample_sum / n)
    resampled_means.sort()

    alpha = 1.0 - confidence
    lo_index = int((alpha / 2) * n_resamples)
    hi_index = min(int((1 - alpha / 2) * n_resamples), n_resamples - 1)

    return BootstrapResult(
        point_estimate=point_estimate,
        ci_low=resampled_means[lo_index],
        ci_high=resampled_means[hi_index],
        n=n,
    )
