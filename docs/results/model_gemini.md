# Eval results — `model_gemini`

> **The most informative negative result in the matrix (D87).** Dev, k=1, Gemini
> `gemini-3.6-flash`, $0.04 spent. **14 repairs applied — nearly double `graph`'s 8 — and
> `pass_rate` moved by exactly zero** (0.396, the codemod floor).
>
> That is a cleaner cross-provider finding than anything in D78: repair *activity* is not
> repair *value*. Groq's 8 patches took `graph` to 0.542 by fixing `Aiven-Open__rohmu` and
> `madkote__fastapi-plugins`; Gemini's 14 fixed nothing measurable, either because the
> patches were wrong or because they landed where they could not help.
>
> Cross-model hazard applies (see main.md): this arm differs from `graph` in BOTH provider
> and nothing else, which is what makes the comparison meaningful here — but N=7 repos and
> the whole `graph` advantage rests on 2 of them.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.31

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.221 [0.079, 0.382] (n=7/7) line jaccard, 0.555 [0.359, 0.759] (n=7/7) symbol precision, 0.672 [0.519, 0.823] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.2959 | 10 | 0.019 | 0.344 | 0.407 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0172 | 3 | 0.564 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
