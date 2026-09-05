# Eval results — `no_t1`

> **Full-matrix re-run 2026-09-05, fourth arm in the same coordinated matrix run —
> zero clone timeouts (fourth consecutive clean arm).** `no_t1` disables T1 by design
> (D62), so repair (T2/T3) is the only mechanism that could fix anything, same as every
> prior run. Quota happened to be fully closed for this specific arm's window: every
> repo needing repair hit an immediate 429 (`Aiven-Open__rohmu`, `SupImDos__pydantic-argparse`,
> `iscc__iscc-core`, `madkote__fastapi-plugins`, `cmudig__draco2`, `okfn__opendataeditor`).
> `eyurtsev__kor` unaffected either way (`preexisting`, D37). Honest variance, not a
> regression — the clone-cache fix has nothing to do with Gemini's own quota window,
> and this arm's real-repair luck simply ran out this round.

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
