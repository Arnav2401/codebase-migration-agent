# Eval results — `embedding`

> **Full-matrix re-run 2026-09-05, third arm in the same coordinated matrix run.**
> `sentence-transformers` needed reinstalling again (uninstalled after the last round,
> per the established install-when-needed pattern). Zero clone timeouts — third
> consecutive arm confirming D70's fix. All 7 repos got a real result this time (no
> dependency-related failures, unlike the prior full-matrix attempt).
>
> Real signal: `Aiven-Open__rohmu` and `cmudig__draco2` each got a real `repair_applied`
> (`fix_class_def`), both zero effect on `pass_rate`. `iscc__iscc-core` reproduced its
> `repair_rejected` corrupt-patch failure yet again (twice) — now confirmed identically
> across `graph`, `wholefile`, AND `embedding` in this same session, a genuinely
> well-established finding independent of retrieval strategy. `SupImDos__pydantic-argparse`
> and `madkote__fastapi-plugins` hit read timeouts; `okfn__opendataeditor` hit the 429
> wall. Real total cost: $0.25.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.25

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0588 | 2 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0655 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.1267 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
