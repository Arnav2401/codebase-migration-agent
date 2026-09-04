# Eval results — `no_t1`

> **Re-run 2026-09-04 — genuinely re-attempted (stale cache cleared first, not a
> resumed skip), but quota-blocked again.** `no_t1` disables T1 (`enable_t1=False`,
> docs/decisions.md D62 — confirmed again this run: every repo logged `edits_applied=0`),
> so repair (T2/T3) is the ONLY mechanism that could fix anything. This time every repo
> that needed repair got an immediate 429 (`Aiven-Open__rohmu`,
> `SupImDos__pydantic-argparse`, `iscc__iscc-core`, `madkote__fastapi-plugins`,
> `cmudig__draco2`, `okfn__opendataeditor`) — `eyurtsev__kor` is the one exception, and
> only because its sole failure classified as `preexisting` (D37's routing rule correctly
> skips repair for an all-preexisting diagnosis — nothing to fix, not a quota casualty).
> Net result unchanged from the original run: with T1 off and T2/T3 quota-blocked,
> nothing had a chance to fix anything, again — this arm has now failed to get a real
> measurement twice in a row. Numbers are byte-identical to the original run and to
> `t1_only`'s own (deterministic, network-free) result, for the same underlying reason
> the original caveat gave: T1's edits (when it runs at all) didn't change whether any
> currently-failing test passed, on this corpus slice.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again,
nothing could fix anything — see caveat above)

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
