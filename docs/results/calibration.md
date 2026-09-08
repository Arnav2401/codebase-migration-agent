# Confidence calibration

> **The score ranks, but it does not calibrate — and it is over-confident exactly where it
> claims most certainty (docs/decisions.md D92).** Actual pass rate does rise with predicted
> confidence (0.02 → 0.15 → 0.50 → 0.44), so the score carries *some* signal. But the
> top bucket holds 37 of 51 runs at a mean predicted 0.946 against a mean actual 0.442, a
> +0.504 gap. A tool that opened PRs on this score would open them confidently and be wrong
> more than half the time.
>
> **The cause is measurement coverage, not weighting.** `mechanical` (weight 0.40) and
> `symbol_coverage` (0.15) are both unmeasured here — 55% of the intended signal — so the
> score collapses onto `easy_classes`, which is high whenever failures are import errors,
> which they usually are. The weights were NOT tuned to close the gap: doing that would fit
> the dev split and produce a well-behaved plot with no more real content.
>
> **The concrete fix** is to make `mechanical` measurable by recording per-source changed-line
> counts on the trace's `patch` events (they already carry `source` and `files_changed`), then
> deriving the fraction from the trace rather than leaving it None. That is the highest-weight
> component and the one that most directly separates "deterministic codemod did this" from
> "the model wrote this freehand" — the distinction D85 showed matters most.

Confidence calibration (predicted vs actual pass rate)

      bucket    n  predicted   actual     gap  plot
0.00-0.25    1      0.000    0.022  -0.022  |PA                                       |
0.25-0.50    9      0.412    0.153  +0.260  |      A         P                        |
0.50-0.75    4      0.642    0.497  +0.144  |                    A     P              |
0.75-1.00   37      0.946    0.442  +0.504  |                  A                   P  |

P = mean predicted confidence, A = mean actual pass rate, * = they coincide.
Positive gap = OVER-confident, the direction that matters for opening PRs.

Components unmeasured in this run and redistributed: mechanical, symbol_coverage. See docs/decisions.md D92 -- an unmeasured component is not scored as zero, because that would shift every prediction by a constant and make the plot look well-behaved while being uniformly wrong.
