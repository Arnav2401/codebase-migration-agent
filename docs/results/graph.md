# Eval results — `graph`

> **Full-matrix re-run 2026-09-05, immediately after D70's clone-cache fix merged.**
> `clone_cache/` was empty at the start of this run, so all 7 repos needed a fresh remote
> clone — and every one succeeded cleanly, zero timeouts. This is the confirming
> evidence for D70: the prior full-matrix run (docs/decisions.md, same date, earlier)
> hit the 300s clone timeout on 5 of these same 7 repos across multiple arms; this run
> and the four that followed it (`wholefile`/`embedding`/`no_t1`/`no_triage`, all sharing
> this same populated cache) had zero clone failures anywhere.
>
> Gemini quota was genuinely open this round, and this is the richest real-signal
> `graph` run yet: `iscc__iscc-core` reproduced its exact `repair_rejected` failure
> (`corrupt patch at line 392`) TWICE — a third+ sighting of this specific repeatable
> failure mode. `SupImDos__pydantic-argparse` and `cmudig__draco2` each got a real
> `repair_applied` with zero effect on `pass_rate` (yet more D69 confirmations).
> `madkote__fastapi-plugins` is the richest single data point of this whole project:
> EIGHT files got a real `repair_applied` (`fix_import`, real cost) in one attempt, plus
> one `repair_rejected` for touching a test file (I1 correctly enforced) — and
> `pass_rate` still didn't move. `Aiven-Open__rohmu` and `okfn__opendataeditor` both hit
> a 120s Gemini read timeout (not quota, not a rejection). Real total cost: $0.35.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.35

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0419 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0083 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.1660 | 3 |
| madkote__fastapi-plugins | 0.000 | False | 0.1331 | 2 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
