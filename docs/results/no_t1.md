# Eval results — `no_t1`

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear.**
> `no_t1` disables T1 by design (D62), so repair (T2/T3) is the only mechanism that could
> fix anything, same as every prior run of this arm. Only 2 of 7 repos got a real result
> this round; the other 5 hit the same git-clone-timeout pattern documented in
> `wholefile.md`'s own caveat (took over an hour for just this arm). `eyurtsev__kor` —
> unaffected either way (`preexisting`, D37). `cmudig__draco2` — repair was genuinely
> ATTEMPTED (not skipped), but hit a 120s Gemini read timeout rather than a clean 429 or
> a real response; with T1 off, that means nothing had a chance to fix `cmudig__draco2`
> this round for a DIFFERENT reason than usual (a timeout, not exhausted quota or a
> disabled tier). Table below has only 2 rows.

**2 repos** — 0 full green, mean pass rate 0.920, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
