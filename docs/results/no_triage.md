# Eval results — `no_triage`

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear —
> the one arm this round that got all 7 repos checked out and tested cleanly, no clone
> timeouts.** Every repo needing repair hit the 429 wall (`madkote__fastapi-plugins`,
> `SupImDos__pydantic-argparse`, `iscc__iscc-core`, `Aiven-Open__rohmu`, `cmudig__draco2`,
> `okfn__opendataeditor`). `eyurtsev__kor` again took the genuinely different
> `triage=False` code path (D37's all-preexisting skip is disabled, so repair was
> actually attempted) and got `agent.repair_no_target` — same real, non-quota outcome as
> the previous round's confirmation of this code path, reproduced again. Fully
> quota-blocked overall; numbers below are the T1-only-shaped degenerate result.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 2 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
