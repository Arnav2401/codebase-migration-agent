# Eval results — `model_groq`

> **Re-run 2026-09-04 — genuinely re-attempted (stale cache cleared first), and it
> reproduces the original finding almost exactly.** Groq isn't Gemini-quota-dependent
> (a separate provider, D48), so this arm doesn't share the other arms' 429-wall problem
> — the same real capacity limitation from the original run shows up again instead: 4 of
> 7 repos (`Aiven-Open__rohmu`, `madkote__fastapi-plugins`, `iscc__iscc-core`,
> `okfn__opendataeditor`) hit `413 Client Error: Payload Too Large` — the graph-retrieved
> prompt exceeds Groq's request size limit for this model, same as before.
> `eyurtsev__kor` again correctly skips repair (its one failure is `preexisting`, D37's
> routing rule).
>
> **The real finding reproduces too: two applied repairs, neither changed pass_rate,
> again.** `SupImDos__pydantic-argparse` got a real `agent.repair_applied`
> (`missing_t1_rule`) and stayed at 0.0, exactly as before. `cmudig__draco2` got a real
> `agent.repair_applied` (`fix_class_def`) and landed at the same 0.884 T1-only baseline
> as before, iterations=2 both times. Costs are near-identical to the original run
> (SupImDos $0.0005, cmudig__draco2 $0.0012) — not byte-identical (token counts vary
> slightly run to run even at temperature=0), but the same magnitude and the same
> zero-effect outcome. This confirms the original run's finding wasn't a fluke: for this
> specific pair of repair attempts on this corpus slice, mechanically accepted patches
> reliably don't flip any test from failing to passing. Still N=2 successful attempts,
> still too small to generalize about `graph` retrieval or repair in general — the other
> 5 repos still never get a real attempt (4 payload-too-large, 1 correctly skipped).

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0005 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0012 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
