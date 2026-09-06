# Eval results — `embedding`

> **Re-run 2026-09-06, third arm in the same fully quota-blocked re-run round.**
> `sentence-transformers` reinstalled again per D61's install-when-needed pattern. Same
> quota wall as the other arms: `SupImDos__pydantic-argparse`, `madkote__fastapi-plugins`,
> and `iscc__iscc-core` hit `429`; `Aiven-Open__rohmu` and `okfn__opendataeditor` hit a
> transient DNS resolution failure on `generativelanguage.googleapis.com`;
> `cmudig__draco2` hit `429`. Zero `repair_applied`. One minor, non-fatal hiccup: a
> `clone_cache_fetch_failed` warning on `okfn__opendataeditor` (git fetch on the cache
> exited 128, coinciding with the same DNS-blip window hitting the Gemini calls) — the
> cache was reused successfully anyway and the repo still scored normally, so this is
> not a repeat of the pre-D70 clone-timeout problem, just noted for completeness. 7/7
> repos otherwise served straight from `clone_cache/` with no timeout. No new
> real-repair signal beyond the prior full-matrix round already documented for this arm
> (`iscc__iscc-core`'s corrupt-patch rejection, etc.).

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
