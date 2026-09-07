# Eval results — `no_t1`

> **Nothing ran in this arm. Every number below is the untouched baseline.** `no_t1`
> disables T1 by design (D62), so repair is the only mechanism that could change anything
> — and all 21 cells spent **$0.00**, every repair call quota-blocked (D48). T1 off plus
> repair blocked means no code was modified at all, which is why this is the only arm
> still reporting the pre-D73 signature: mean 0.266, zero repos full green, and
> diff-similarity of exactly 0.000 across all 7 repos (nothing was written, so there is
> nothing to compare against the human's fix). See docs/decisions.md D74.
>
> It is still useful as a control, precisely because it is untouched. Read against
> `t1_only` it isolates what the codemods do: `eyurtsev__kor` sits at 0.955 here and drops
> to 0.506 under T1 — so T1 is unambiguously the thing that breaks that repo, and
> `graph`'s repair restoring it to 0.955 is repair undoing T1's damage. `cmudig__draco2`
> is 0.884 here vs 0.878 under T1. But the ablation this arm is *for* — what the codemods
> buy relative to an LLM working alone — needs repair to actually run, and it did not.

**7 repos (21 repo x seed runs)** — 0 full green (every seed passed), mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.000 [0.000, 0.000] (n=7/7) line jaccard, 0.000 [0.000, 0.000] (n=7/7) symbol precision, 0.000 [0.000, 0.000] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 [0.884, 0.884] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 [0.955, 0.955] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
