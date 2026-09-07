# Eval results — `no_t1`

> **T1 disabled by design (D62), so repair is the only mechanism — and it got exactly one
> call through.** 1 repair applied, 6 failed to 429s, $0.0009 spent. Mean 0.266, zero full
> green: the single applied patch did write something (diff-similarity is now 0.001/0.036/
> 0.005 rather than a flat 0.000) but moved no repo's pass_rate.
>
> Still most useful as the untouched control. Against `t1_only` it isolates the codemods
> cleanly: `eyurtsev__kor` 0.955 here vs 0.506 there proves T1 is what breaks that repo;
> `iscc__iscc-core` 0.000 here vs 1.000 there proves T1 is what fixes that one.
>
> The ablation this arm exists for — what codemods buy versus an LLM alone — needs repair to
> run on more than one repo, and quota did not allow it.

**7 repos** — 0 full green (every seed passed), mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.001 [0.000, 0.002] (n=7/7) line jaccard, 0.036 [0.000, 0.107] (n=7/7) symbol precision, 0.005 [0.000, 0.016] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0009 | 2 | 0.005 | 0.250 | 0.037 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
