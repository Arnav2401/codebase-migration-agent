# Eval results — `wholefile`

> **Full-matrix re-run 2026-09-05, right after `graph` in the same coordinated matrix
> run.** `clone_cache/` was already fully populated from `graph`'s run — zero clone
> timeouts, zero remote clone traffic at all for this arm (every checkout was a local
> clone from the cache). Confirms D70's fix generalizes across arms, not just the one
> that happens to populate the cache first.
>
> Real signal: `Aiven-Open__rohmu` got a real `repair_applied` on two files
> (`fix_class_def`) with zero effect on `pass_rate`. `iscc__iscc-core` reproduced its
> `repair_rejected` corrupt-patch failure again (twice) — now seen in every arm that's
> gotten a real attempt this round. `madkote__fastapi-plugins` got two more real repairs,
> still zero effect. `SupImDos__pydantic-argparse`, `okfn__opendataeditor`, and
> `cmudig__draco2` each hit a 120s Gemini read timeout instead of quota or rejection.
> Real total cost: $0.15.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.15

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0414 | 2 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0741 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.0385 | 2 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
