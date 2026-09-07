# Eval results — `embedding`

> **This arm did not measure embedding retrieval. Do not cite it as an embedding result.**
> All 21 cells spent **$0.00**: every repair call was quota-blocked (D48), so the retrieval
> strategy under test never selected context for a model call that happened. What ran was
> T1's codemod and nothing else — which is why every number in this file is *identical* to
> `t1_only`'s (mean 0.396, same per-repo values, same diff-similarity to three decimals).
> That identity is the tell, not a finding: it is what an unexercised ablation looks like
> (docs/decisions.md D74).
>
> The graph-vs-embedding comparison this arm exists to support — phase-5-eval.md calls it
> "the resume claim" — therefore remains **unmeasured**. `graph` bought real repair in one
> seed and this arm bought none, so any delta between them is a quota schedule, not a
> retrieval comparison. Post-D73; before that fix every patch was a silent no-op and the
> whole file was void.

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.216 [0.075, 0.376] (n=7/7) line jaccard, 0.541 [0.330, 0.755] (n=7/7) symbol precision, 0.616 [0.380, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
