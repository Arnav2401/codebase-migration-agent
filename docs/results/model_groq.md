# Eval results — `model_groq`

> **The arm with the most real repair activity this project has ever recorded — and it
> changed nothing (docs/decisions.md D78).** Dev split, k=1, Groq `openai/gpt-oss-120b`
> with the D75 prompt cap, which is what finally made this arm viable: **20 repairs
> applied** (against 1 in the previous round), 5 failed, 2 prompts trimmed, zero 413s. The
> cap converted an arm that was mostly measuring a payload bug into one that genuinely ran.
>
> **Mean pass_rate 0.396 — exactly `t1_only`'s.** `SupImDos__pydantic-argparse` absorbed 20
> applied patches over 21 iterations and finished at `0.000`, the same value it holds in
> every other arm including the one that never calls a model. That 21-iteration churn is
> itself the most actionable lead in the corpus: it suggests the loop re-fixing the same
> failure class without converging, rather than the model simply being unable.
>
> Unlike the NVIDIA arms, cost here is real ($0.0116, all of it on `SupImDos`), so spend is
> still a usable "did repair run" signal for this row.
>
> Not a provider comparison with `graph` in the useful sense: both arms landed on the same
> number, so what this pair actually shows is that the null result reproduces across two
> independent providers and model families.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.01

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.217 [0.077, 0.376] (n=7/7) line jaccard, 0.546 [0.344, 0.756] (n=7/7) symbol precision, 0.621 [0.392, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0116 | 21 | 0.010 | 0.286 | 0.074 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
