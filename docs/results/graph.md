# Eval results — `graph`

> **Caveat — this run does not measure the `graph` retrieval strategy.** All 7 repos hit
> Gemini's free-tier 429 quota wall on every single repair attempt (`agent.repair_failed`,
> "429 Client Error: Too Many Requests") — T2/T3 never successfully ran once. What's below
> is effectively a **T1-only** measurement wearing the `graph` config's name, not a
> real read on whether graph-based context retrieval helps repair. `usd_spent` is $0.00
> across every repo for the same reason: a 429 response is never billed. This is a known,
> previously-documented failure mode of the free tier (docs/decisions.md D48) — not a bug
> in this run, and not something worth re-running immediately in the hope the quota
> refills predictably (D48 found it doesn't). Reported here rather than hidden, per this
> project's own stated preference for an honest degenerate result over a quietly
> re-rolled one. Re-run once quota allows to get a real T1+T2+T3 `graph` measurement.

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
