# Eval results — `no_triage`

> **Did not measure the triage ablation.** All 7 repair calls 429'd (0 applied), so
> `triage=False` had no repair call to route and nothing to change. What ran was T1 alone,
> which is why the mean matches `t1_only` at 0.396.
>
> Phase 4's justification remains unmeasured post-D73. Note the diff-similarity numbers
> differ slightly from `t1_only`'s (0.188 vs 0.216 line jaccard) purely because
> `eyurtsev__kor` reports 0.000 here — a measurement artifact of which files were touched,
> not evidence of a triage effect.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.188 [0.037, 0.364] (n=7/7) line jaccard, 0.464 [0.214, 0.721] (n=7/7) symbol precision, 0.512 [0.235, 0.767] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
