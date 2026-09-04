# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Caveat on `graph` and `wholefile` below — neither measures its retrieval strategy.**
> Every repo in both arms hit Gemini's free-tier 429 quota wall on every repair attempt
> (docs/decisions.md D48's previously-documented failure mode) — T2/T3 never successfully
> executed once in either arm, so both rows are effectively the same **T1-only**
> measurement, and both match `t1_only`'s own genuine (not quota-degenerate — this arm
> never calls a model at all, by design) row exactly. See each arm's own
> `docs/results/<arm>.md` for the full explanation. `graph`/`wholefile` both need a
> genuine re-run once quota allows for a real comparison — that comparison is the actual
> point of running those two arms at all.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| graph | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |
| t1_only | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |
| wholefile | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |

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

### t1_only

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

### wholefile

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
