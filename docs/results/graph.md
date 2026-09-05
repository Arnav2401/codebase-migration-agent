# Eval results — `graph`

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear.**
> A cheap probe call succeeded, confirming quota was open — but the very first real
> attempt (this one) hit `429 Client Error` on every single repo needing repair
> (`madkote__fastapi-plugins`, `Aiven-Open__rohmu`, `iscc__iscc-core`, `cmudig__draco2`,
> `okfn__opendataeditor`); `SupImDos__pydantic-argparse` hit a 120s read timeout instead
> (Gemini accepted the connection but never responded). `eyurtsev__kor` unaffected either
> way (`preexisting`, D37). The quota window that let the probe through appears to have
> closed again within moments of real usage starting — consistent with D48's own
> "narrow and largely closed" characterization, just demonstrated freshly after a much
> longer wait than any prior attempt this session. All 7 repos DID get checked out and
> tested cleanly this time (no clone issues for this arm specifically). Numbers below are
> the T1-only-shaped degenerate result, byte-identical to `t1_only`.

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
