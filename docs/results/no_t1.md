# Eval results — `no_t1`

> **Re-run 2026-09-04 (fourth attempt) — genuinely re-attempted (stale cache cleared
> first), quota-blocked again.** T1 stays off as designed (`edits_applied=0` on every
> repo, fourth run in a row confirming D62's `enable_t1=False` wiring). Every repo that
> needed repair hit an immediate 429; `eyurtsev__kor` is unaffected either way
> (`preexisting`, D37). With T1 off and T2/T3 quota-blocked, nothing had a chance to fix
> anything — same outcome as all three prior attempts, numbers byte-identical to
> `t1_only`'s deterministic result. Unlike `wholefile`'s own fourth attempt (which
> finally got one real repair through this round, see docs/results/wholefile.md), this
> arm still hasn't landed inside Gemini's quota window even once across four tries.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again,
fourth attempt — see caveat above)

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
