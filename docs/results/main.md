# Eval results — main

> **FINAL Phase 5 matrix (docs/decisions.md D87).** All seven arms, dev split, k=1, one
> configuration (D77-scoped, so nothing is averaged across configs).
>
> **`graph` 0.542 vs `t1_only` 0.396** — the repair tier adds real value now (D85/D86),
> after every prior round in this project had the two identical (D78, D84). But the entire
> spread across the matrix rests on **two repos**: `Aiven-Open__rohmu` 0.000 → 0.872 under
> `graph` alone, and `madkote__fastapi-plugins` 0.370 → 0.519 under `graph` and `wholefile`.
> Every other repo is identical in every arm.
>
> **Three arms measured nothing.** `embedding` (0 repairs applied), `no_triage` (0) and
> `no_t1` (0) had every repair call rate-limited, so their numbers are the "nothing ran"
> value — `embedding` and `no_triage` equal `t1_only` for that reason, NOT because those
> strategies perform like the codemods. The retrieval ablation (phase-5-eval.md's "resume
> claim") is still unmeasured after six attempts across five providers; quota, not
> engineering, has been the binding constraint throughout.
>
> **`model_gemini` is the sharpest result here:** 14 repairs applied, nearly double
> `graph`'s 8, and zero movement. Repair activity is not repair value.
>
> **Held-out: 0.028** (`graph.test.md`), unchanged and uninformative — zero repairs executed
> there, one rate-limited and one with no findable target. The I5 budget (3 runs) is now
> exhausted, so whether the dev improvement generalizes is unmeasured and unmeasurable
> without a new split.
>
> Note for whoever regenerates this file: `report_cli` rewrites it, so this caveat is
> hand-maintained. D85/D86/D87 are the durable record.

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden. N is the number of distinct repos, not repo x seed cells, even for an arm run under multiple seeds (docs/decisions.md D72).

> **These arms do not all run the same model — do not read across the split.** Each row differs from the others in more than the thing its name calls out, so a difference between two arms on opposite sides of the split confounds the ablation with the model change and measures neither. Compare only within a model:
>
> - `gemini-3.6-flash`: `model_gemini`
> - `openai/gpt-oss-120b`: `embedding`, `graph`, `no_t1`, `no_triage`, `t1_only`, `wholefile`
>
> Why an arm runs the model it does varies, and this warning deliberately does NOT guess: an arm may name a second provider because comparing providers IS its ablation, or because the first one was rate-limited and the arm was re-run elsewhere to be measurable at all. Both produce the same table and the same hazard above.
>
> Separately, and load-bearing for reading ANY row here: Gemini's free tier on this project is 20 requests/day and trickle-refills rather than resetting cleanly (docs/decisions.md D48), so an arm can score every one of its cells while every single repair call returns 429. Such an arm reports real test outcomes but no real repair activity — its numbers are T1's deterministic codemod alone, not the tier or retrieval strategy its name describes. The tell is the cost column: a near-zero spend next to a full N means nothing was actually repaired, and that row is measuring T1, whatever its name says.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | symbol_recall (mean [95% CI], n measured) |
|---|---|---|---|---|---|---|---|
| embedding | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| graph | 7 | 0.542 [0.259, 0.807] | 0.143 [0.000, 0.429] | $0.00 | 0.093 [0.005, 0.253] (n=7/7) | 0.234 [0.071, 0.443] (n=7/7) | 0.410 [0.114, 0.740] (n=7/7) |
| model_gemini | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.04 | 0.221 [0.079, 0.379] (n=7/7) | 0.555 [0.358, 0.758] (n=7/7) | 0.672 [0.519, 0.825] (n=7/7) |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| no_triage | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| t1_only | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| wholefile | 7 | 0.418 [0.146, 0.717] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.542 [0.328, 0.755] (n=7/7) | 0.620 [0.386, 0.822] (n=7/7) |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.872 | False | 0.0031 | 2 | 0.018 | 0.267 | 0.889 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0057 | 3 | 0.018 | 0.385 | 0.185 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.519 | False | 0.0020 | 3 | 0.560 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### model_gemini

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.2959 | 10 | 0.019 | 0.344 | 0.407 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0172 | 3 | 0.564 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### no_triage

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### t1_only

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### wholefile

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.519 | False | 0.0019 | 3 | 0.548 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
