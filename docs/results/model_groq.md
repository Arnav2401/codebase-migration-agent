# Eval results — `model_groq`

> **Note — this arm is NOT quota-degenerate like the others, but it isn't a clean
> measurement either.** Groq hit a completely different limitation than Gemini's 429
> wall: 2 of 7 repos (`SupImDos__pydantic-argparse`, `cmudig__draco2`) got a REAL
> `agent.repair_applied` — real tokens, real (tiny) cost, `violations=[]`. The other 4 hit
> `413 Client Error: Payload Too Large` — the graph-retrieved prompt exceeded Groq's
> request size limit for this model, a genuine capacity constraint of this
> provider/model/retrieval combination, not exhaustion. `eyurtsev__kor` again correctly
> skipped repair (its one failure is `preexisting`, D37's routing rule).
>
> **The real, slightly deflating finding: neither of the 2 applied repairs changed
> pass_rate.** `cmudig__draco2` re-ran tests after the fix (`iterations=2`) and landed at
> the exact same 0.884 T1-only baseline; `SupImDos__pydantic-argparse` stayed at 0.0. Both
> repairs were mechanically accepted (no rejected patch, no invariant violation) but
> neither one flipped a single test from failing to passing in this run. That's real
> signal about this specific pair of repair attempts on this corpus slice — not a
> conclusion about repair or the graph strategy in general, since N=2 successful attempts
> is far too small to generalize from, and the other 5 repos never got a real attempt at
> all this round (4 payload-too-large, 1 correctly skipped).

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0005 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0011 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
