# Eval results — `embedding`

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear.**
> Cache was cleared first. This attempt ALSO needed a `sentence-transformers` reinstall
> partway through (it had been uninstalled again after D67's fix verification, per the
> established install-when-needed / uninstall-after pattern) — the first sub-attempt
> failed 4 repos outright on the missing dependency before that was caught and fixed.
> After reinstalling: only 2 of 7 repos got a real result. `eyurtsev__kor` — unaffected
> either way (`preexisting`, D37). **`cmudig__draco2` got a genuine `agent.repair_applied`
> this time** (`fix_class_def`, real cost $0.0675, `violations=[]`) — mechanically
> accepted, but `pass_rate` landed at the exact same `0.884` T1-only baseline as every
> prior run: a THIRD independent confirmation of D69's finding (applies cleanly, fixes
> nothing), now with `embedding` retrieval specifically in the mix alongside `graph` and
> `model_groq`. The other 5 repos hit the same git-clone-timeout/failure pattern
> documented in `wholefile.md`'s own caveat (4 timeouts, 1 `exit status 128`) — this
> session's repeated cloning appears to be triggering real throttling, not code failures.
> Table below has only 2 rows.

**2 repos** — 0 full green, mean pass rate 0.920, total cost $0.07

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| cmudig__draco2 | 0.884 | False | 0.0675 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
