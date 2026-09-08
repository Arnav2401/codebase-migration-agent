# Confidence calibration

> **Making the highest-weight component measurable made calibration WORSE, and that is the
> finding (docs/decisions.md D93).** `mechanical` (weight 0.40) is now derived from real
> per-source changed-line counts on the trace instead of being unmeasured. The middle
> bucket's gap went from +0.14 to +0.50, and every bucket is over-confident.
>
> **The formula's premise is false on this corpus.** phase-6-trace-pr.md weights "fraction
> of changed lines from mechanical codemods" most heavily, on the reasoning that
> deterministic codemods are more trustworthy than model-written code. But deterministic is
> not the same as correct, and this project has already measured the counter-example:
> D84 showed T1 BREAKS `eyurtsev__kor`, dropping it 0.955 → 0.506. Under the formula that
> repo is 100% mechanical (37 T1 lines, 0 model) and scores confidence **1.000** against an
> actual 0.506. `Aiven-Open__rohmu` under `t1_only` is the starkest: 93 T1 lines, 0 model,
> confidence **1.000**, actual **0.000**.
>
> So the component is measured correctly and means the wrong thing. A trustworthy score
> would need a signal about whether the codemods *helped* — which is the pass rate itself,
> and therefore unavailable at PR time, when the score has to be produced. That is a real
> limitation of predicting confidence for this task, not a tuning problem.

Confidence calibration (predicted vs actual pass rate)

      bucket    n  predicted   actual     gap  plot
0.25-0.50    6      0.415    0.080  +0.335  |   A             P                       |
0.50-0.75    5      0.652    0.157  +0.495  |      A                   P              |
0.75-1.00   38      0.943    0.462  +0.481  |                  A                   P  |

P = mean predicted confidence, A = mean actual pass rate, * = they coincide.
Positive gap = OVER-confident, the direction that matters for opening PRs.

Components unmeasured in this run and redistributed: mechanical, symbol_coverage. See docs/decisions.md D92 -- an unmeasured component is not scored as zero, because that would shift every prediction by a constant and make the plot look well-behaved while being uniformly wrong.
