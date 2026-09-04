# Eval results — `wholefile`

> **Re-run 2026-09-04, right after `graph`'s own re-run in the same session — genuinely
> re-attempted (cache cleared first, not a stale resume), but quota ran out again.**
> `graph`'s re-run (docs/results/graph.md) got real Gemini responses through — several
> real `repair_applied`/`repair_rejected` calls, $0.30 total cost. This run started
> immediately after and every repo that needed repair got a 429 straight away
> (`SupImDos__pydantic-argparse`, `madkote__fastapi-plugins`, `iscc__iscc-core`,
> `Aiven-Open__rohmu`, `cmudig__draco2`, `okfn__opendataeditor`) — the daily quota window
> `graph` had just been using apparently closed again before `wholefile`'s turn came up.
> `eyurtsev__kor` is unaffected either way (repair correctly skipped, D37's
> all-preexisting rule). Numbers below are byte-identical to the old quota-blocked table
> this doc used to report, and to `graph`'s own pre-2026-09-04 T1-only numbers — expected,
> since T1 doesn't depend on retrieval strategy and nothing got past T1 this round either.
> Still a genuine T1+T2+T3 attempt, still degenerate by outcome — re-run again once quota
> allows for a real `wholefile` measurement, ideally BEFORE spending quota on `graph` in
> the same session (D48: quota doesn't refill predictably or quickly).

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again,
see caveat above)

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
