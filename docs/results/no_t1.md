# Eval results — `no_t1`

> **Nothing ran. Every number here is the untouched baseline.** T1 is disabled by design
> (D62) so repair is the only mechanism available, and all 6 repair calls were 429'd by
> NVIDIA's quota mid-sweep (0 applied). No code was modified, which is why this is the only
> arm still reporting the no-op signature: mean 0.266, zero full green, diff-similarity
> exactly 0.000 across all 7 repos.
>
> Still valuable as the untouched control. Read against `t1_only` it isolates the codemods:
> `eyurtsev__kor` sits at 0.955 here and 0.506 there, so **T1 is unambiguously what breaks
> that repo**; `iscc__iscc-core` is 0.000 here and 1.000 there, so T1 is equally
> unambiguously what fixes that one.
>
> The ablation this arm exists for — what the codemods buy versus an LLM working alone —
> needs repair to actually run, and it did not.

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
