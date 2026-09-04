# Eval results — `graph`

> **Re-run 2026-09-04, replacing the earlier quota-blocked attempt this doc used to
> report.** Gemini answered for real this time (no blanket 429 wall), so this is a
> genuine T1+T2+T3 `graph` measurement — still 0 full green, but for real, repo-specific
> reasons this time, not one uniform quota casualty:
>
> - `iscc__iscc-core` — repair genuinely tried twice, both `repair_rejected` with the
>   identical error (`corrupt patch at line 392`): the model's proposed patch for
>   `iscc_core/options.py` doesn't parse as a valid diff against the graph-retrieved
>   context, consistently, not a one-off. A real, repeatable failure mode worth looking at
>   if `graph` gets picked up again.
> - `Aiven-Open__rohmu` — a repair WAS applied (`fix_class_def`, two files rewritten) but
>   didn't change `pass_rate` at all (stayed 0.000) — mechanically accepted, didn't fix
>   the actual failure.
> - `SupImDos__pydantic-argparse` — same pattern: one repair applied
>   (`missing_t1_rule`), zero effect on pass_rate.
> - `cmudig__draco2` and `okfn__opendataeditor` — repair was attempted but hit Gemini's
>   429 wall partway through THIS run (quota exhausted mid-run, not from the start —
>   different from every earlier arm's all-7-blocked pattern). `cmudig__draco2`'s T1-only
>   result (0.884) still stands since repair never got a response to act on.
> - `madkote__fastapi-plugins` — repair hit a genuine 120s read timeout, not quota or a
>   rejection — Gemini just didn't respond in time.
> - `eyurtsev__kor` — unchanged from every prior run: T1-only, repair correctly skipped
>   (D37's all-preexisting routing rule), 0.955.
>
> Net: real signal that `graph` retrieval gets repair attempts through cleanly (no crash,
> no malformed prompt) but doesn't obviously flip failures to passing on this corpus
> slice — though N is small and 2 of 7 repos never got a clean attempt at all this round.
> Cost is real this time too ($0.30, vs. every prior $0.00 quota-blocked run).

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.30 (see caveat above — this
is now a real, not quota-degenerate, measurement)

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0897 | 2 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0358 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.1793 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
