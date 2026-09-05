# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden.

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear.**
> A cheap probe call succeeded, confirming the quota window had opened — but real usage
> across `graph`/`wholefile`/`no_t1`/`no_triage` mostly hit the 429 wall again within
> moments, consistent with D48's "narrow and largely closed" characterization holding
> even after a much longer wait than any prior attempt this session. It wasn't a total
> shutout: `cmudig__draco2` got a genuine `agent.repair_applied` in `embedding`
> (`fix_class_def`, $0.0675) — a THIRD independent confirmation of D69's "applies
> cleanly, fixes nothing" finding, now spanning `graph`, `embedding`, and `model_groq`.
>
> **A separate, new, and arguably more actionable finding from this run: a persistent
> `git clone` timeout pattern.** `Aiven-Open__rohmu`, `SupImDos__pydantic-argparse`,
> `iscc__iscc-core`, `madkote__fastapi-plugins`, and `okfn__opendataeditor` repeatedly hit
> a hard 300-second clone timeout across `wholefile`, `embedding`, and `no_t1` this
> round — `eyurtsev__kor` and `cmudig__draco2` never did. `wholefile`/`embedding`/`no_t1`
> below have fewer than 7 rows as a direct result (4, 2, and 2 respectively) — missing
> repos have no fabricated result standing in for them. Given this session cloned the
> same ~7 repos dozens of times over many hours tonight, this looks like GitHub
> rate-limiting or throttling this machine's IP, not a code bug — worth a real fix (e.g.
> a persistent local clone cache) before the next full-matrix attempt.
>
> `t1_only` and `model_groq` were correctly NOT re-run this round (already settled,
> D69) — everything else was a genuine re-attempt with stale cache cleared first. See
> each arm's own `docs/results/<arm>.md` for full detail.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost |
|---|---|---|---|---|
| embedding | 2 | 0.920 [0.884, 0.955] | 0.000 [0.000, 0.000] | $0.03 |
| graph | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| model_groq | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| no_t1 | 2 | 0.920 [0.884, 0.955] | 0.000 [0.000, 0.000] | $0.00 |
| no_triage | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| t1_only | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 |
| wholefile | 4 | 0.460 [0.000, 0.920] | 0.000 [0.000, 0.000] | $0.00 |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| cmudig__draco2 | 0.884 | False | 0.0675 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |

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
| SupImDos__pydantic-argparse | 0.000 | False | 0.0008 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0012 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |

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
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
