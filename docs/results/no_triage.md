# Eval results — `no_triage`

> **Re-run 2026-09-04 — genuinely re-attempted (stale cache cleared first), same quota
> wall, but reproduces the same real distinct behavior as before.** 6 of 7 repos hit
> Gemini's 429 quota wall on repair immediately (`Aiven-Open__rohmu`,
> `SupImDos__pydantic-argparse`, `iscc__iscc-core`, `madkote__fastapi-plugins`,
> `cmudig__draco2`, `okfn__opendataeditor`). `eyurtsev__kor` is again the exception with
> the same genuinely different code path: `triage=False` disables D37's "skip repair
> entirely on an all-preexisting diagnosis" check, so repair was actually ATTEMPTED here
> (`iterations=2`, same as the original run) rather than skipped outright — and it again
> produced `agent.repair_no_target` (no findable target file), not a quota casualty, the
> exact same outcome as the original run. Confirms the original finding wasn't a fluke:
> the `use_triage=False` fallback path is reliably live and reliably hits the same
> no-target wall on this repo, independent of quota state. Every number below is
> byte-identical to the original run, and otherwise the same T1-only-shaped result as
> `graph`/`wholefile`/`t1_only`/`no_t1`.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again
except eyurtsev__kor's confirmed no-target attempt, see caveat above)

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
