# Eval results — `no_triage`

> **Re-run 2026-09-06, fifth and final arm in the same fully quota-blocked re-run
> round.** All 5 repos needing repair hit `429` (`SupImDos__pydantic-argparse`,
> `madkote__fastapi-plugins`, `iscc__iscc-core`, `Aiven-Open__rohmu`, `cmudig__draco2`,
> `okfn__opendataeditor`). Zero `repair_applied`. The one real, quota-independent
> signal this arm can produce regardless of Gemini's state held again: `eyurtsev__kor`
> took the `triage=False` code path (D37's all-preexisting skip disabled) and got
> `agent.repair_no_target` a third consecutive time across this project's runs — this is
> now a well-established, stable property of the code path, not luck. Zero clone
> timeouts across all five arms in this round (35/35 repo-attempts served from
> `clone_cache/`, D70 holds completely).
>
> Taking this round as a whole: every real repair call across all 5 arms x 7 repos = 35
> attempts hit 429, a read-timeout, or a transient DNS resolution failure — the initial
> cheap 1-token quota probe that triggered this run succeeded, but the window closed
> again before any real repair call landed. This is an honest negative result, not a
> failure to hide, and it sharpens D48's finding: a successful cheap probe does not
> predict that subsequent real usage will succeed, even seconds later. The prior
> full-matrix round (still documented in this project's git history and decision log)
> remains the richest real-repair dataset collected for this project; this round adds no
> new real-repair signal beyond that dataset, only confirming that D70's clone-cache fix
> continues to hold and that `eyurtsev__kor`'s `repair_no_target` finding is now backed by
> a third independent reproduction.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 2 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
