# Eval results — `no_t1`

> **Caveat — this run does not measure `no_t1`'s intended arm either.** `no_t1` disables
> T1 (`enable_t1=False`, docs/decisions.md D62 — confirmed live: every repo logged
> `edits_applied=0`) so repair (T2/T3) is the ONLY mechanism that could fix anything. But
> repair hit the same Gemini 429 quota wall as every other arm this round for every repo
> that attempted it; `eyurtsev__kor` is the one exception, and only because its sole
> failure classified as `preexisting` (D37's routing rule correctly skips repair entirely
> for an all-preexisting diagnosis — nothing to fix, not a quota casualty). Net result:
> with T1 off and T2/T3 quota-blocked, literally nothing had a chance to fix anything this
> round, for a different reason than `graph`/`wholefile`'s own caveat.
>
> **A genuinely surprising thing this run DOES show, worth flagging rather than
> smoothing over:** every one of these 7 pass rates is byte-identical to `t1_only`'s own
> run, even for repos where T1 applied real edits in that run (e.g. `Aiven-Open__rohmu`,
> 8 edits applied). That means, at least for this corpus slice, T1's mechanical rewrites
> didn't change whether any baseline-passing test kept passing or not — plausible if T1's
> edits landed in files/code paths the currently-failing tests don't actually exercise
> (a single collection error can block a whole file's tests regardless of how many
> *other* files got modernized), but this run alone doesn't prove that explanation; it's
> an observation, not a conclusion, and worth a real look once non-degenerate T2/T3 data
> exists to compare against.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (nothing could fix anything, see caveat above)

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
