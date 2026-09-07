# Eval results — `graph`

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.431, total cost $0.31

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.217 [0.071, 0.382] (n=7/7) line jaccard, 0.540 [0.323, 0.760] (n=7/7) symbol precision, 0.614 [0.387, 0.805] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.2005 | 5.3 | 0.002 | 0.216 | 0.074 |
| cmudig__draco2 | 0.918 [0.878, 1.000] (k=3 seeds) | 1/3 | 0.0214 | 2.0 | 0.502 | 0.815 | 0.667 |
| eyurtsev__kor | 0.655 [0.506, 0.955] (k=3 seeds) | 0/3 | 0.0633 | 1.3 | 0.163 | 0.522 | 0.636 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.420 [0.370, 0.519] (k=3 seeds) | 0/3 | 0.0286 | 1.7 | 0.554 | 0.734 | 0.778 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
