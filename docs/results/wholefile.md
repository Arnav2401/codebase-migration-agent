# Eval results — `wholefile`

> **Re-run 2026-09-04 (third attempt) — genuinely re-attempted (stale cache cleared
> first), quota-blocked again.** Every repo needing repair hit an immediate 429
> (`madkote__fastapi-plugins`, `SupImDos__pydantic-argparse`, `Aiven-Open__rohmu`,
> `iscc__iscc-core`, `cmudig__draco2`, `okfn__opendataeditor`); `eyurtsev__kor` is
> unaffected either way (repair correctly skipped, D37). This arm has now failed to get
> a real T1+T2+T3 measurement three times running — Gemini's free-tier daily quota
> window is evidently narrow and this arm hasn't yet landed inside it. Numbers are
> byte-identical to every prior attempt. Contrast with `graph`'s 2026-09-04 re-run
> (docs/results/graph.md), which DID get real repair attempts through in the same
> session window — `wholefile` simply hasn't had the lucky timing yet. Re-run again
> once quota allows, ideally as the FIRST arm attempted in a session rather than after
> others have already spent the window.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again,
third attempt — see caveat above)

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
