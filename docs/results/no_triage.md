# Eval results — `no_triage`

> **Caveat — same quota wall, but this run DOES show one real, distinct thing.** 6 of 7
> repos hit Gemini's 429 quota wall on repair (docs/decisions.md D48), same degenerate
> pattern as every other arm this round. `eyurtsev__kor` is the exception, and it's a
> genuinely different code path than the other arms' handling of it: with `triage=False`,
> D37's "skip repair entirely on an all-preexisting diagnosis" check is disabled by
> design, so repair was actually ATTEMPTED here (a real second `run_tests` iteration ran —
> `iterations=2`, vs. every other arm's `1`) rather than skipped outright. It still didn't
> fix anything (`agent.repair_no_target` — no findable target file, not a quota casualty),
> but this is real evidence the `use_triage=False` fallback path (D37/D38's pre-triage
> behavior) is live and doing something different, not just an assumption. Every number
> below is otherwise the same T1-only-shaped result as `graph`/`wholefile`/`t1_only`.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (repair quota-blocked except one real no-target attempt, see caveat above)

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
