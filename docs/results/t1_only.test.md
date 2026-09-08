# Eval results — `t1_only`

> **Held-out split, test-split run 2 of 3 (I5). Codemods only, no model, $0.00.**
> Mean pass_rate **0.028** — `lnbits__lnurl` 0.056, `isaacharrisholt__quiffen` 0.000.
>
> **Identical to `graph`'s held-out result, repo for repo** (`docs/results/graph.test.md`,
> which had T1 + LLM repair and applied a real patch). This is D78's null result
> re-established on data nobody tuned against: **the entire held-out capability of this
> system is T1's deterministic codemods.** The LLM repair tier contributed exactly zero.
>
> Why this run was worth one of three permitted test-split runs: it decomposes the headline
> 0.028 into "codemods" versus "codemods + LLM", which is the one question the headline
> alone cannot answer. It also cost no API quota, so it spent budget that is scarce (I5)
> rather than budget that is unreliable (provider limits).

**2 repos** — 0 full green (every seed passed), mean pass rate 0.028, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.100 [0.021, 0.178] (n=2/2) line jaccard, 0.718 [0.636, 0.800] (n=2/2) symbol precision, 0.218 [0.103, 0.333] (n=2/2) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| isaacharrisholt__quiffen | 0.000 | False | 0.0000 | 1 | 0.178 | 0.636 | 0.333 |
| lnbits__lnurl | 0.056 | False | 0.0000 | 1 | 0.021 | 0.800 | 0.103 |
