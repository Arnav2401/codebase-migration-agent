# Eval results — `graph`

> **First live run of the k=3 seed-variance protocol (docs/decisions.md D72),
> 2026-09-07.** `--seeds 0,1,2` against a freshly cleared `graph` arm — 21 repo×seed
> cells (7 repos × 3 seeds), zero clone timeouts throughout (D70 holds at 3x the usual
> per-arm load). The report.py grouping itself worked as designed: every repo below
> collapses to one row, not three.
>
> **The headline finding: every repo's `pass_rate` is IDENTICAL across all 3 seeds** —
> every range in the table below is `[x, x]`, zero measured variance. But most of that
> "zero variance" is trivial, not evidence of reproducibility: `SupImDos__pydantic-argparse`,
> `madkote__fastapi-plugins`, and `iscc__iscc-core` had EVERY seed's repair attempt hit
> `429`/`503` (0/3 real attempts each) — there was nothing to vary. `eyurtsev__kor`
> correctly skips repair every time (`preexisting`, D37) — also nothing to vary.
>
> The one genuine reproducibility data point is `cmudig__draco2`: it got a REAL
> `repair_applied` (`fix_class_def`, same file) in 2 of its 3 seeds (seed 0 and seed 2;
> seed 1 hit a quota block) — and the two calls produced literally different model
> output (`tokens_out=698` vs `tokens_out=649`, so not byte-identical despite
> `temperature=0`), yet both landed at the exact same `pass_rate=0.884`. That's real,
> if narrow (n=1 repo, k=2 independent live attempts), evidence that this pipeline
> reproduces at the OUTCOME level even when the underlying LLM call itself isn't
> perfectly deterministic. `Aiven-Open__rohmu` and `okfn__opendataeditor` each got
> exactly one real repair (1/3 seeds; the other 2 seeds were quota-blocked) — extending
> D69 (repair applies cleanly, zero effect on `pass_rate`) but not adding a second
> reproducibility data point, since there's no second real attempt on the same repo to
> compare against.
>
> **Acceptance criterion status:** phase-5-eval.md's "full dev-split run reproduces to
> within seed variance across two invocations" is honestly PARTIALLY met — the one repo
> that actually got two independent real attempts reproduced exactly, but N=1 repo is a
> thin basis for the whole-arm claim, and getting a cleaner answer needs Gemini's quota
> open enough for more repos to land 2+ real attempts each. Still, the direction of the
> evidence (zero variance where it could be measured) is consistent with the harness
> being genuinely deterministic downstream of the LLM call, not encouraging otherwise.
>
> **New, notable, and NOT yet fully explained:** every diff-similarity metric
> (`diff_line_jaccard`, `symbol_precision`, `symbol_recall`) reads exactly `0.000` for
> every one of the 7 repos, including the 3 that got a real, cleanly-applied repair
> (`rohmu`, `draco2`, `okfn`) — this is the FIRST time these metrics have ever been
> measured for real (D71 wired the reporting; this run is the first data). A flat
> 0.000 across every repo, even ones with a genuinely applied patch, is worth treating
> as a real finding (this pipeline's fixes may share literally nothing — not one line,
> not one symbol — with the human's actual fix) but also as one to sanity-check further
> before leaning on it hard: it hasn't yet been cross-checked against a manual read of
> even one actual diff pair.

**7 repos (21 repo x seed runs)** — 0 full green (every seed passed), mean pass rate 0.266, total cost $0.21

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.000 [0.000, 0.000] (n=7/7) line jaccard, 0.000 [0.000, 0.000] (n=7/7) symbol precision, 0.000 [0.000, 0.000] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0963 | 1.3 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 [0.884, 0.884] (k=3 seeds) | 0/3 | 0.0176 | 1.7 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 [0.955, 0.955] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0986 | 1.3 | 0.000 | 0.000 | 0.000 |
