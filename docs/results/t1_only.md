# Eval results — `t1_only`

> **The one arm whose $0.00 is correct by design, and the reference every other row should
> be read against.** `t1_only` never calls a model (D62), so zero spend is the expected
> result, not a quota failure — and all 3 seeds are identical because deterministic
> codemods are deterministic. This is the only arm in this round whose numbers mean
> precisely what its name says. Post-D73: before that fix these patches never reached
> disk and this arm scored the untouched baseline.
>
> **Read as the T1 baseline, it says the codemods do real and mixed work:**
> - `iscc__iscc-core` 0.000 → **1.000**, full green on T1 alone. The clearest win in the
>   corpus, and repair deserves no credit for it.
> - `eyurtsev__kor` 0.955 → **0.506**. T1 actively breaks this repo; compare `no_t1`,
>   which leaves it untouched at 0.955, and `graph` seed 0, where repair restores it to
>   0.955. A specific codemod rule is wrong here and this is where to look.
> - `cmudig__draco2` 0.884 → 0.878, marginally worse; `graph`'s repair takes it to 1.000.
>
> Caution when comparing arms: `embedding` and `no_triage` report numbers *identical* to
> this file's, not because their strategies match T1 but because their repair calls were
> entirely quota-blocked, leaving T1 as all they ran (docs/decisions.md D74). An arm
> matching `t1_only` exactly is evidence it measured nothing of its own.

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.216 [0.075, 0.376] (n=7/7) line jaccard, 0.541 [0.330, 0.755] (n=7/7) symbol precision, 0.616 [0.380, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
