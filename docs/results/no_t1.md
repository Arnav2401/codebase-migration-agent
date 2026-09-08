# Eval results — `no_t1`

> **Dev, k=1, matched config. 0.266 — the untouched baseline (D87).** T1 disabled by
> design (D62) and all 6 repair calls rate-limited, so no code was modified at all. This is
> the only arm still showing the no-op signature: zero full green, diff-similarity 0.000.
>
> Useful precisely because it is untouched: against `t1_only` it isolates the codemods.
> `eyurtsev__kor` 0.955 here vs 0.506 there — T1 unambiguously BREAKS that repo;
> `iscc__iscc-core` 0.000 here vs 1.000 there — T1 unambiguously fixes that one.

**7 repos** — 0 full green (every seed passed), mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.000 [0.000, 0.000] (n=7/7) line jaccard, 0.000 [0.000, 0.000] (n=7/7) symbol precision, 0.000 [0.000, 0.000] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
