# Eval results — `wholefile`

> **Re-run 2026-09-04 (fifth attempt) — quota-blocked again, after the fourth attempt's
> first real signal.** Every repo needing repair hit an immediate 429 this time
> (`SupImDos__pydantic-argparse`, `madkote__fastapi-plugins`, `Aiven-Open__rohmu`,
> `iscc__iscc-core`, `cmudig__draco2`, `okfn__opendataeditor`); `eyurtsev__kor` is
> unaffected either way (D37). This doesn't undo the fourth attempt's real finding
> (`madkote__fastapi-plugins` got a genuine `agent.repair_applied` that didn't change
> `pass_rate`) — it's the same quota-timing story every arm shows across this session's
> repeated attempts: one real result stands regardless of how later re-attempts land.
> Numbers below are the degenerate T1-only shape, byte-identical to `t1_only`.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked this
attempt — the fourth attempt got real signal through, see git history on this file)

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
