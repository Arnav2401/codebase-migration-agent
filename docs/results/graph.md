# Eval results — `graph`

> **Re-run 2026-09-06, after a multi-hour Gemini-quota wait loop — came back fully
> quota-blocked.** The wait loop's own cheap 1-token probe succeeded moments before this
> run started (and `docker info` was verified up), but every one of the 7 real repair
> calls this arm made hit a wall anyway: `SupImDos__pydantic-argparse` and
> `madkote__fastapi-plugins` got `429 Too Many Requests`, `Aiven-Open__rohmu` and
> `iscc__iscc-core` got the same 429 followed later by a transient DNS resolution failure
> on retry, `cmudig__draco2` and `okfn__opendataeditor` hit real infra errors (DNS
> resolution failure / no route to host) rather than quota specifically. Zero
> `repair_applied` anywhere. This strengthens D48's finding rather than contradicting
> it: a successful cheap probe call does not guarantee the quota window stays open long
> enough for real, larger repair calls seconds later.
>
> Zero clone timeouts (7/7 repos, all served from `clone_cache/`) — D70's fix continues
> to hold. This run adds no new real-repair signal; the prior full-matrix round (still
> documented in this project's decision log and git history) remains the richest real
> dataset collected for this arm.

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
