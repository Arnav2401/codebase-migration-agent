# Eval results — `wholefile`

> **Caveat — this run does not measure the `wholefile` retrieval strategy.** Same failure
> mode as `docs/results/graph.md`: all 7 repos hit Gemini's free-tier 429 quota wall on
> every repair attempt (docs/decisions.md D48) — T2/T3 never successfully ran once. This
> is effectively a **T1-only** measurement, and its per-repo numbers are byte-identical to
> `graph`'s own T1-only run: expected, since T1 doesn't depend on retrieval strategy at
> all, and retrieval only matters once repair actually runs. Re-run once quota allows for
> a real T1+T2+T3 `wholefile` measurement — and a real graph-vs-wholefile comparison,
> which is the whole point of this arm (phase-5-eval.md: "Is retrieval needed at all, or
> does a big context window solve it?").

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (T1-only, see caveat above)

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
