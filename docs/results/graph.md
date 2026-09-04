# Eval results — `graph`

> **Re-run 2026-09-04 (fourth attempt) — quota-blocked again, same pattern as the third
> attempt.** Every repo needing repair hit an immediate 429; `eyurtsev__kor` is
> unaffected either way (D37). This arm's outcome across four attempts now shows a clear
> split: one attempt (the second) got real Gemini responses through — real repair
> attempts, $0.30 cost, a consistently unparseable-patch failure mode on
> `iscc__iscc-core`, two mechanically-accepted repairs that didn't change `pass_rate` —
> and three attempts (first, third, fourth) hit the 429 wall immediately. That's not a
> flaky arm; it's a direct readout of Gemini's free-tier quota window being narrow and
> largely closed relative to how often this session has been hitting it. The one real
> result stands on its own merits regardless of how the quota lottery goes on any given
> re-attempt. Numbers below are the degenerate T1-only shape, byte-identical to
> `t1_only`/every quota-blocked arm.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked this
attempt, 3 of 4 total attempts have been — see caveat above)

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
