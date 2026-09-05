# Eval results — `wholefile`

> **Full-matrix re-run 2026-09-05, after waiting ~6.5 hours for Gemini quota to clear.**
> Cache was cleared first (genuine re-attempt). The 4 repos below all hit Gemini's 429
> wall on repair (`SupImDos__pydantic-argparse`, `madkote__fastapi-plugins`) or were
> unaffected either way (`eyurtsev__kor`, `preexisting`; `cmudig__draco2`'s failure was
> never re-tested). **A NEW, separate finding: 3 of 7 repos never even got checked out**
> — `Aiven-Open__rohmu`, `iscc__iscc-core`, `okfn__opendataeditor` all hit a `git clone`
> timeout at exactly 300 seconds. This is a real infra issue, not a code bug: this
> session cloned these same ~7 repos dozens of times over many hours tonight (every arm,
> every re-attempt), and this specific timeout pattern — always the same repos, always
> exactly the connect/transfer timeout — is consistent with GitHub rate-limiting or
> throttling this machine's IP after sustained repeated cloning, not a one-off network
> blip. Worth a real look (e.g. a persistent local clone cache instead of a fresh clone
> per repo per run) before running this matrix again. Table below has only 4 rows, not
> 7 — the 3 timed-out repos have no result to report this round, and none was fabricated
> to fill the gap.

**4 repos** — 0 full green, mean pass rate 0.460, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
