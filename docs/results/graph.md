# Eval results — `graph`

> **The only arm in this round that actually bought repair — and only in seed 0.**
> Post-D73 (before that fix every patch was a silent no-op and all of this was void).
> Seed 0 spent $0.3138 with real repair on 4/7 repos and scored mean 0.499; seeds 1 and 2
> spent $0.0000, repaired nothing, and scored 0.396 — which is `t1_only`'s mean exactly,
> because with the quota gone that is all they were. **The headline 0.431 below is
> therefore `mean(0.499, 0.396, 0.396)`: one run of T1+repair averaged with two runs of T1
> alone. No pipeline has a 0.431 pass rate.** See docs/decisions.md D74.
>
> For the same reason the per-repo ranges are NOT seed variance. `cmudig__draco2`
> [1.0, 0.878, 0.878], `eyurtsev__kor` [0.955, 0.506, 0.506], `madkote__fastapi-plugins`
> [0.519, 0.37, 0.37] — each is high in the seed that had quota and identical in the two
> that did not. phase-5-eval.md's seed-variance criterion is not met by this run.
>
> **What IS real here comes from seed 0, and it is the most useful result the project has
> produced.** Read against `t1_only` and `no_t1`:
> - `eyurtsev__kor` — untouched 0.955, T1 alone 0.506, T1+repair 0.955. The codemod breaks
>   this repo and repair puts it back exactly. That is a concrete argument for the repair
>   tier, and a concrete bug report against that T1 rule.
> - `cmudig__draco2` — untouched 0.884, T1 alone 0.878, T1+repair **1.000**, full green.
>   Repair reaches a state T1 cannot.
> - `iscc__iscc-core` — full green under T1 alone, in every arm; repair is not the actor.
> - `SupImDos__pydantic-argparse` and `madkote__fastapi-plugins` took real repair spend in
>   seed 0 and still did not reach green.

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.431, total cost $0.31

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.217 [0.071, 0.382] (n=7/7) line jaccard, 0.540 [0.323, 0.760] (n=7/7) symbol precision, 0.614 [0.387, 0.805] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.2005 | 5.3 | 0.002 | 0.216 | 0.074 |
| cmudig__draco2 | 0.918 [0.878, 1.000] (k=3 seeds) | 1/3 | 0.0214 | 2.0 | 0.502 | 0.815 | 0.667 |
| eyurtsev__kor | 0.655 [0.506, 0.955] (k=3 seeds) | 0/3 | 0.0633 | 1.3 | 0.163 | 0.522 | 0.636 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.420 [0.370, 0.519] (k=3 seeds) | 0/3 | 0.0286 | 1.7 | 0.554 | 0.734 | 0.778 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
