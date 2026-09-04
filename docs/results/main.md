# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Caveat on `graph` below — not a real read on the retrieval strategy.** Every one of
> its 7 repos hit Gemini's free-tier 429 quota wall on every repair attempt this run
> (docs/decisions.md D48's previously-documented failure mode) — T2/T3 never successfully
> executed once, so this row is effectively a **T1-only** measurement, not a measurement
> of graph-based retrieval. See `docs/results/graph.md`'s own caveat for the full
> explanation. Only one of seven planned arms has been run at all so far; this table will
> fill in as the rest do, and `graph` itself needs a genuine re-run once quota allows.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| graph | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |

## Per-repo appendix

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
