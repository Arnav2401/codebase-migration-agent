# Eval results — `graph`

> **Re-run 2026-09-04 (third attempt) — genuinely re-attempted (stale cache cleared
> first), but quota-blocked this time, unlike the second attempt.** Every repo needing
> repair hit an immediate 429; `eyurtsev__kor` is unaffected either way (repair correctly
> skipped, D37). This is the opposite outcome from this arm's own prior re-run (see git
> history on this file / docs/decisions.md), which DID get real Gemini responses through
> — real repair attempts, real cost ($0.30), a consistently unparseable-patch failure
> mode on `iscc__iscc-core`, two mechanically-accepted repairs that didn't change
> `pass_rate`. That real result isn't invalidated by this attempt; it just shows this
> arm's outcome depends on which side of Gemini's free-tier daily quota window a given
> run happens to land on, run to run, even for the SAME arm. Numbers below are the
> degenerate T1-only shape, byte-identical to `t1_only`/every quota-blocked arm this
> round — not a regression, just quota timing this attempt.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked this
attempt — see caveat above; a prior attempt got real signal through)

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
