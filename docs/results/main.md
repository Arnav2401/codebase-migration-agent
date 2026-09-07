# Eval results — main

> **Final Phase 5 dev-split state (docs/decisions.md D78/D79).** Machinery is now correct:
> patches actually reach disk (D73), the prompt budget holds payloads under provider limits
> (D75 — zero 413s), and each arm is reported against exactly one configuration (D77). Six
> ablation arms run on Groq `openai/gpt-oss-120b`; `model_gemini` is the provider contrast.
>
> **The headline is a null result.** `graph` applied 5 real patches and scored mean
> **0.396** — the exact number `t1_only` gets while never calling a model. Counting earlier
> rounds on other providers, **29 applied patches across three providers have moved
> pass_rate by zero** (D78). On this corpus the deterministic codemods do all the measurable
> work, and the LLM repair tier — as currently prompted, targeted and validated — adds
> nothing measurable on top.
>
> **Most ablations still did not run.** `no_triage`, `wholefile`, `embedding` and
> `model_gemini` had every repair call 429'd; `no_t1` got exactly one through. Their
> identical 0.396 rows are the signature of an unexercised ablation, not a result. Five
> attempts across four providers (Gemini, Groq, OpenAI, NVIDIA) have not produced a sweep
> where quota survived all seven arms — free-tier limits, not engineering, are the binding
> constraint.
>
> **Seed variance (k=3) was measured only for `t1_only`**, where 7/7 repos were byte-identical
> across seeds. That establishes the harness is deterministic; it says nothing about LLM
> sampling, since that arm has no LLM.
>
> **There is no test-split number and cannot be one yet: the corpus contains zero
> `split="test"` repos** (D79). That is Phase 0's unticked box, not a Phase 5 omission, and
> relabelling dev repos that have been tuned against for the whole project would produce a
> contaminated number that merely looked held-out.
>
> Per-repo facts stable across every round: `iscc__iscc-core` 0.000 → 1.000 under T1 alone;
> `eyurtsev__kor` 0.955 → 0.506, broken by a codemod and never recovered by repair;
> `SupImDos__pydantic-argparse` absorbed 29 patches across providers and never left 0.000.
>
> Note for whoever regenerates this file: `report_cli` rewrites it from scratch, so this
> caveat is hand-maintained and will vanish on the next run. D73–D79 are the durable record.

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
| graph | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.218 [0.077, 0.373] (n=7/7) | 0.553 [0.355, 0.756] (n=7/7) | 0.626 [0.410, 0.817] (n=7/7) |
| model_gemini | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.001 [0.000, 0.002] (n=7/7) | 0.036 [0.000, 0.107] (n=7/7) | 0.005 [0.000, 0.016] (n=7/7) |
| no_triage | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| t1_only | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |
| wholefile | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |

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
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0042 | 6 | 0.012 | 0.333 | 0.111 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### model_gemini

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0009 | 2 | 0.005 | 0.250 | 0.037 |
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
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
