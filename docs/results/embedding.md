# Eval results — `embedding`

> **Did not measure embedding retrieval. Do not cite as an embedding result.** All 6 repair
> calls 429'd (0 applied) after NVIDIA's quota ran out mid-sweep, so the strategy under test
> never fed a call that happened. Numbers are identical to `t1_only` (0.396, same per-repo
> values, same diff-similarity) because T1 is all that ran.
>
> The graph-vs-embedding comparison — phase-5-eval.md calls it "the resume claim" —
> therefore remains **unmeasured**. And per D78 it now faces a prior problem: `graph`'s own
> repairs moved pass_rate by zero this round, so on current evidence there may be no
> pass-rate difference for either retrieval strategy to make.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.216 [0.075, 0.376] (n=7/7) line jaccard, 0.541 [0.330, 0.755] (n=7/7) symbol precision, 0.616 [0.380, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
