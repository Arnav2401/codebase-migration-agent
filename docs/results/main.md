# Eval results — main

> **These are the first valid numbers this project has ever produced (2026-09-07).
> Every result predating them is void — see docs/decisions.md D73.** `apply_patch` was
> silently no-op'ing every T1 codemod and every T2/T3 repair: `git apply` resolved diff
> paths against this project's own enclosing `.git` rather than the scratch overlay,
> printed `Skipped patch` to stdout, exited 0, and the harness recorded `applied=True`
> with nothing written to disk. Every earlier run measured the untouched baseline, which
> is why all seven arms used to report identical per-repo pass rates (mean 0.266
> everywhere, zero repos full green, diff-similarity exactly 0.000 across the board).
> Seven ablations agreeing to three decimal places was the bug announcing itself.
>
> What changed once patches actually landed: `t1_only` 0.266 → 0.396 (the codemods do
> real work), `graph` 0.266 → 0.431 with `full_green` 0.190, and `iscc__iscc-core` went
> from an eternal 0.000 to 1.000, full green on all 3 seeds. It is not all good news, and
> that is the useful part: `eyurtsev__kor` DROPPED from 0.955 to 0.655 — the agent
> actively breaks a repo that was mostly passing, a regression the no-op bug had hidden
> for the project's entire history.
>
> Note for whoever regenerates this file: `report_cli` rewrites it from scratch, so this
> caveat is hand-maintained and will vanish on the next run. D73 is the durable record.

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden. N is the number of distinct repos, not repo x seed cells, even for an arm run under multiple seeds (docs/decisions.md D72).

> **These arms do not all run the same model — do not read across the split.** Each row differs from the others in more than the thing its name calls out, so a difference between two arms on opposite sides of the split confounds the ablation with the model change and measures neither. Compare only within a model:
>
> - `gemini-3.6-flash`: `embedding`, `graph`, `no_t1`, `no_triage`, `t1_only`, `wholefile`
> - `openai/gpt-oss-120b`: `model_groq`
>
> Why an arm runs the model it does varies, and this warning deliberately does NOT guess: an arm may name a second provider because comparing providers IS its ablation, or because the first one was rate-limited and the arm was re-run elsewhere to be measurable at all. Both produce the same table and the same hazard above.
>
> Separately, and load-bearing for reading ANY row here: Gemini's free tier on this project is 20 requests/day and trickle-refills rather than resetting cleanly (docs/decisions.md D48), so an arm can score every one of its cells while every single repair call returns 429. Such an arm reports real test outcomes but no real repair activity — its numbers are T1's deterministic codemod alone, not the tier or retrieval strategy its name describes. The tell is the cost column: a near-zero spend next to a full N means nothing was actually repaired, and that row is measuring T1, whatever its name says.

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | symbol_recall (mean [95% CI], n measured) |
|---|---|---|---|---|---|---|---|
| embedding | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| graph | 7 | 0.431 [0.137, 0.739] | 0.190 [0.000, 0.476] | $0.04 | 0.217 [0.069, 0.382] (n=7/7) | 0.540 [0.321, 0.759] (n=7/7) | 0.614 [0.397, 0.810] (n=7/7) |
| model_groq | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.01 | 0.219 [0.081, 0.374] (n=7/7) | 0.543 [0.333, 0.755] (n=7/7) | 0.658 [0.495, 0.818] (n=7/7) |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| no_triage | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| t1_only | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| wholefile | 7 | 0.404 [0.132, 0.700] | 0.143 [0.000, 0.429] | $0.00 | 0.217 [0.075, 0.374] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.617 [0.386, 0.820] (n=7/7) |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.2005 | 5.3 | 0.002 | 0.216 | 0.074 |
| cmudig__draco2 | 0.918 [0.878, 1.000] (k=3 seeds) | 1/3 | 0.0214 | 2.0 | 0.502 | 0.815 | 0.667 |
| eyurtsev__kor | 0.655 [0.506, 0.955] (k=3 seeds) | 0/3 | 0.0633 | 1.3 | 0.163 | 0.522 | 0.636 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.420 [0.370, 0.519] (k=3 seeds) | 0/3 | 0.0286 | 1.7 | 0.554 | 0.734 | 0.778 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |

### model_groq

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0426 | 16.3 | 0.023 | 0.267 | 0.333 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 [0.884, 0.884] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 [0.955, 0.955] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |

### no_triage

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |

### t1_only

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |

### wholefile

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.420 [0.370, 0.519] (k=3 seeds) | 0/3 | 0.0145 | 1.7 | 0.554 | 0.734 | 0.778 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
