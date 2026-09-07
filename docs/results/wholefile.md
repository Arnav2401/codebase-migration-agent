# Eval results — `wholefile`

> **Barely exercised: one repo, in one seed, bought repair.** Post-D73. Seed 0 spent
> $0.0145 on `madkote__fastapi-plugins` alone; seeds 1 and 2 spent $0.0000 and degenerated
> to T1-only, scoring 0.396 — `t1_only`'s exact mean. The headline 0.404 below is
> `mean(0.418, 0.396, 0.396)`, a blend of two different pipelines rather than a property of
> either (docs/decisions.md D74). The single per-repo range, `madkote__fastapi-plugins`
> [0.519, 0.37, 0.37], is quota state and not seed variance: high where repair ran,
> identical where it did not.
>
> phase-5-eval.md singles this arm out as the one "a sharp interviewer will ask for" —
> does a naive whole-file dump tie graph retrieval? **That question is still open.**
> `graph` bought repair on 4 repos and this arm on 1, so the gap between them reflects how
> much quota each happened to get, not how well either retrieves. The one real data point:
> `madkote__fastapi-plugins` reached 0.519 here with whole-file context, the same value
> `graph` reached on that repo — a single tie on a single repo, which is worth noting and
> nowhere near enough to answer the question.

**7 repos (21 repo x seed runs)** — 1 full green (every seed passed), mean pass rate 0.404, total cost $0.01

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.217 [0.075, 0.378] (n=7/7) line jaccard, 0.541 [0.330, 0.756] (n=7/7) symbol precision, 0.617 [0.381, 0.814] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 [0.878, 0.878] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 [0.506, 0.506] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 [1.000, 1.000] (k=3 seeds) | 3/3 | 0.0000 | 1.0 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.420 [0.370, 0.519] (k=3 seeds) | 0/3 | 0.0145 | 1.7 | 0.554 | 0.734 | 0.778 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.233 | 1.000 | 0.364 |
