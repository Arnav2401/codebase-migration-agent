# Eval results — `no_t1`

> **Re-run 2026-09-06, fourth arm in the same fully quota-blocked re-run round.**
> `no_t1` disables T1 by design (D62), so repair is the only mechanism that could fix
> anything here, same as ever. `SupImDos__pydantic-argparse`, `Aiven-Open__rohmu`,
> `madkote__fastapi-plugins`, `iscc__iscc-core`, and `okfn__opendataeditor` all hit
> `429`; `cmudig__draco2` got a 429 followed by a `Read timed out (read timeout=120)`
> on retry roughly 25 minutes later. Zero `repair_applied`. `eyurtsev__kor` unaffected
> either way (`preexisting`, D37). Zero clone timeouts (D70 holds). No new real-repair
> signal beyond the prior full-matrix round already documented for this arm.

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
