# Eval results — `graph`

**2 repos** — 0 full green (every seed passed), mean pass rate 0.028, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.100 [0.021, 0.178] (n=2/2) line jaccard, 0.718 [0.636, 0.800] (n=2/2) symbol precision, 0.218 [0.103, 0.333] (n=2/2) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| isaacharrisholt__quiffen | 0.000 | False | 0.0000 | 2 | 0.178 | 0.636 | 0.333 |
| lnbits__lnurl | 0.056 | False | 0.0000 | 1 | 0.021 | 0.800 | 0.103 |
