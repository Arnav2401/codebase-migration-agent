# Eval results — `graph`

> **Baseline arm. Groq `openai/gpt-oss-120b`, dev split, k=1, $0.0042 spent, 5 repairs
> applied** (6 failed once Groq's quota ran out mid-sweep), zero 413s thanks to the D75 cap.
>
> **Mean pass_rate 0.396 — identical to `t1_only`, which never calls a model at all.** Five
> patches applied cleanly and moved no repo's pass_rate. This is the third independent
> confirmation of docs/decisions.md D78, after 4 patches on NVIDIA and 20 on Groq in earlier
> rounds: 29 applied patches, three providers, zero measurable pass-rate movement. On this
> corpus the deterministic codemods are doing all the measurable work.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.218 [0.077, 0.376] (n=7/7) line jaccard, 0.553 [0.357, 0.758] (n=7/7) symbol precision, 0.626 [0.407, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0042 | 6 | 0.012 | 0.333 | 0.111 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
