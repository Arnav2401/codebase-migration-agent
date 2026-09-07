# Eval results — `model_groq`

> **The one arm whose three seeds are genuinely comparable — and the control that proves
> the others' "seed variance" was quota.** Post-D73. Groq's limits held where Gemini's did
> not, so all three seeds spent about the same ($0.0139 / $0.0140 / $0.0147) and scored
> identically. Compare `graph`, whose seed 0 spent $0.31 and whose seeds 1 and 2 spent
> nothing at all: that arm's spread is a quota schedule, this arm's flatness is what an
> actually-repeated measurement looks like (docs/decisions.md D74).
>
> **But coverage is thin: only 1 of 7 repos (`SupImDos__pydantic-argparse`) got a repair
> call through** — the rest have historically hit Groq's `413 Payload Too Large` on this
> corpus. With six repos unrepaired, the arm mean 0.396 is again just `t1_only`'s number.
>
> **The one real cross-provider result, and it is a negative one.**
> `SupImDos__pydantic-argparse` sits at `pass_rate=0.000` under Groq ($0.0139) *and* under
> Gemini in `graph` ($0.2005 — the single most expensive repo of the round). Two
> providers, real patches genuinely applied post-D73, no movement either way. This is the
> one piece of the old D69 claim ("repairs land and change nothing") that survives onto
> valid data — narrowed from "every repair" to "this repo resists both providers," which
> is a much smaller but actually supported claim.
>
> Not a provider comparison: `graph` bought repair on 4 repos and this arm on 1, so any
> delta between them measures how much quota each got, not Gemini vs Groq.

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.04

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.219 [0.081, 0.376] (n=7/7) line jaccard, 0.543 [0.336, 0.755] (n=7/7) symbol precision, 0.658 [0.494, 0.814] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0426 | 16.3 | 0.023 | 0.267 | 0.333 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 [0.370, 0.370] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
