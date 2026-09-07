# Eval results — `wholefile`

> **Did not measure whole-file retrieval.** All 6 repair calls 429'd (0 applied), so the
> retrieval strategy under test never supplied context to a call that happened. T1 alone
> ran; the mean is `t1_only`'s 0.396.
>
> phase-5-eval.md singles this arm out as the one "a sharp interviewer will ask for" — does
> a naive whole-file dump tie graph retrieval? **Still open, and now open for a sharper
> reason:** `graph` DID run repair this round (4 patches) and still landed on the same
> 0.396, so even a fully-measured `wholefile` would be compared against a baseline where
> retrieval quality made no difference to pass_rate at all (D78).

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.137 [0.035, 0.267] (n=7/7) line jaccard, 0.436 [0.214, 0.687] (n=7/7) symbol precision, 0.506 [0.244, 0.760] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
