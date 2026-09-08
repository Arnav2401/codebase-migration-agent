# Eval results — `wholefile`

> **Dev, k=1, matched config (D87). 0.418, 1 repair applied.** Above `t1_only`'s 0.396
> because of a single repo: `madkote__fastapi-plugins` 0.370 -> 0.519. Every other repo is
> identical to the codemod baseline.
>
> phase-5-eval.md calls this the arm "a sharp interviewer will ask for" — does a naive
> whole-file dump tie graph retrieval? On this run it does NOT: `graph` reaches 0.542 and
> also fixes `Aiven-Open__rohmu` (0.000 -> 0.872), which this arm does not. But that gap is
> one repo wide, and `graph` landed 8 repairs to this arm's 1, so the difference plausibly
> reflects how many calls survived rate limiting rather than retrieval quality. Not a
> settled answer.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.418, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.216 [0.075, 0.376] (n=7/7) line jaccard, 0.542 [0.330, 0.757] (n=7/7) symbol precision, 0.620 [0.381, 0.816] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.519 | False | 0.0019 | 3 | 0.548 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
