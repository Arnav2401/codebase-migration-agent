# Eval results — `graph`

> **One of only two arms in this round that actually exercised repair (docs/decisions.md
> D78).** Dev split, k=1, NVIDIA `moonshotai/kimi-k3` (D76). **4 repairs applied**, 6 failed
> (read timeouts and 429s once NVIDIA's quota ran out mid-sweep), 2 prompts trimmed by the
> D75 budget, and **zero 413s** — the payload bug that used to make most of this corpus
> unrepairable is gone.
>
> **And the result is identical to `t1_only`, row for row.** Mean 0.396 either way. Four
> patches applied cleanly and moved no repo's `pass_rate`. `SupImDos__pydantic-argparse`
> took 4 of them across 5 iterations and stayed at 0.000. Read D78 before citing this: on
> valid post-D73 data, across two providers, repair is not adding measurable pass-rate on
> top of the codemods.
>
> `usd_spent` reads $0.00 for every repo and that is NOT the "nothing ran" tell it is in
> other arms — NVIDIA's catalog is free-credit access, so cost is structurally zero here
> whatever happens (D76). The repair counts above are the real signal.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.217 [0.076, 0.376] (n=7/7) line jaccard, 0.553 [0.357, 0.758] (n=7/7) symbol precision, 0.626 [0.407, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 5 | 0.005 | 0.333 | 0.111 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
