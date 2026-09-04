# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Caveat on `graph`/`wholefile`/`no_t1`/`no_triage` below — none measures what its own
> arm is meant to.** Every repo across all four hit Gemini's free-tier 429 quota wall on
> nearly every repair attempt this round (docs/decisions.md D48). `graph`/`wholefile`
> degenerate to T1-only; `no_t1` (T1 off by design) degenerates to nothing being able to
> fix anything; `no_triage` is 6/7 quota-blocked plus one real (non-quota) `repair_no_target`
> outcome. `model_groq` below is different — a different provider hit a different, real
> limitation (`413 Payload Too Large` on 4/7 repos, not quota exhaustion) and 2/7 repos got
> a genuine `repair_applied` with real (if tiny, ~$0.0016 total) cost. Neither applied
> repair changed pass_rate, which is real signal on this specific pair of attempts, not a
> conclusion about repair in general at N=2. See each arm's own `docs/results/<arm>.md`
> for its full explanation. Everything but `t1_only` needs a genuine re-run once Gemini
> quota allows (and `model_groq`'s 4 payload-too-large repos need EITHER a smaller
> retrieval budget or a model that accepts a larger request to get a real attempt at all).

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| graph | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |
| model_groq | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_triage | 7 | 0.266 [0.003, 0.546] | 0.000 [0.000, 0.000] | $0.00 |
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

### model_groq

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0005 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0011 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

### no_triage

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 2 |
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
