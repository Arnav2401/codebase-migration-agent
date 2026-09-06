# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Re-run 2026-09-06, after a multi-hour Gemini-quota wait loop — came back fully
> quota-blocked.** `graph`, `wholefile`, `embedding`, `no_t1`, and `no_triage` were all
> re-attempted (`model_groq` and `t1_only` intentionally left untouched — settled,
> non-Gemini-dependent). The wait loop's own cheap 1-token quota probe succeeded right
> before this run started, and `docker info` was verified up, but the window closed
> again before any real repair call landed: all 35 repo-attempts (5 arms × 7 repos) hit
> either `429 Too Many Requests`, a `Read timed out`, or a transient DNS resolution
> failure on `generativelanguage.googleapis.com`. Zero `repair_applied` anywhere this
> round. This is an honest negative result, not a failure to hide — it sharpens D48's
> finding that Gemini's free-tier quota trickle-refills unpredictably and that a
> successful cheap probe does not predict subsequent real usage will succeed.
>
> Zero clone timeouts across all 35 attempts — D70's persistent clone-cache fix
> continues to hold completely (one minor, non-fatal `clone_cache_fetch_failed` warning
> during `embedding`, cache reused fine). `no_triage`'s `eyurtsev__kor` `repair_no_target`
> outcome reproduced a third consecutive time — a real, quota-independent signal.
> `model_groq` was NOT re-run this round (its own real-capacity finding is settled at
> five independent runs, see `model_groq.md`).
>
> This round adds no new real-repair signal beyond the prior full-matrix round already
> documented in each arm's own file below and in this project's decision log — that
> earlier round (rich `repair_applied` activity across `Aiven-Open__rohmu`,
> `SupImDos__pydantic-argparse`, `cmudig__draco2`, `madkote__fastapi-plugins`, plus
> `iscc__iscc-core`'s reproducible corrupt-patch rejection) remains the richest real
> dataset collected for this project so far.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| embedding | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| graph | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| model_groq | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_triage | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| t1_only | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| wholefile | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

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
| SupImDos__pydantic-argparse | 0.000 | False | 0.0006 | 2 |
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
