# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Full-matrix re-run 2026-09-05, immediately after D70's clone-cache fix merged —
> a complete clean sweep.** All six re-attempted arms (`graph`, `wholefile`,
> `embedding`, `no_t1`, `no_triage`, `model_groq`) got all 7 repos checked out with ZERO
> clone timeouts, confirming D70's fix: the prior full-matrix run (same date, earlier)
> hit the 300s clone timeout on 5 of these same 7 repos, repeatedly, across multiple
> arms. `clone_cache/` populated once during `graph`'s run and every later arm reused
> it — no further remote clone traffic for the rest of the matrix, including
> `model_groq`'s run, which completed in well under a minute.
>
> Gemini quota was genuinely open for most of this run (closed again for `no_t1`'s
> specific window — honest variance, unrelated to the clone fix). This produced the
> richest real-repair dataset of the whole project: `iscc__iscc-core`'s `repair_rejected`
> corrupt-patch failure (`corrupt patch at line 392`) reproduced identically across
> `graph`, `wholefile`, and `embedding` — a well-established, retrieval-strategy-independent
> finding. Every real `repair_applied` this round — across `Aiven-Open__rohmu`,
> `SupImDos__pydantic-argparse`, `cmudig__draco2`, and `madkote__fastapi-plugins`
> (the last touching EIGHT files in one attempt) — still had zero effect on `pass_rate`,
> extending D69's finding with zero exceptions found yet. `no_triage`'s `eyurtsev__kor`
> `repair_no_target` outcome (the `triage=False` code path) also reproduced a second
> time. `model_groq` was additionally re-run at the user's request and reproduced its
> now-classic finding a FIFTH consecutive time (same 2/7 repos get real, zero-effect
> repairs; same 4/7 hit `413 Payload Too Large`; same 1/7 correctly skipped) — as settled
> a finding as this project has.
>
> `t1_only` correctly not re-run (already settled per D69, never calls a model at all).

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| embedding | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.04 |
| graph | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.05 |
| model_groq | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_triage | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| t1_only | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| wholefile | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.02 |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0588 | 2 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0655 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.1267 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0419 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0083 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.1660 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.1331 | 2 |
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
| Aiven-Open__rohmu | 0.000 | False | 0.0414 | 2 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0741 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.0385 | 2 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
