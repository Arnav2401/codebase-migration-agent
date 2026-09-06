# Eval results — `wholefile`

> **Re-run 2026-09-06, second arm in the same fully quota-blocked re-run round.** Same
> story as `graph`: `madkote__fastapi-plugins`, `Aiven-Open__rohmu`, `okfn__opendataeditor`,
> and `cmudig__draco2` hit `429 Too Many Requests`; `SupImDos__pydantic-argparse` and
> `iscc__iscc-core` got a 429 followed by a `Read timed out (read timeout=120)` on retry.
> Zero `repair_applied`. Zero clone timeouts (7/7 from `clone_cache/`, D70 holds).
> No new real-repair signal beyond the prior full-matrix round already documented for
> this arm.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00

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
