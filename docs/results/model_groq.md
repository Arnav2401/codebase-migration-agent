# Eval results — `model_groq`

> **Re-run 2026-09-04 (third live attempt) — reproduces the same finding a third
> consecutive time.** Groq isn't Gemini-quota-dependent, so this arm keeps hitting its
> own real capacity limit instead: 4 of 7 repos (`madkote__fastapi-plugins`,
> `iscc__iscc-core`, `Aiven-Open__rohmu`, `okfn__opendataeditor`) hit `413 Client Error:
> Payload Too Large` — same repos as both prior attempts. `eyurtsev__kor` again
> correctly skips repair (`preexisting`, D37).
>
> **The core finding holds a third time: the same two repairs apply, neither changes
> pass_rate.** `SupImDos__pydantic-argparse` got a real `agent.repair_applied`
> (`missing_t1_rule`) and stayed at 0.0 — third time running. `cmudig__draco2` got a real
> `agent.repair_applied` (`fix_class_def`) and landed at the same 0.884 T1-only baseline
> — third time running. Costs are again near-identical in magnitude to both prior
> attempts (SupImDos ~$0.0006, cmudig__draco2 ~$0.0012). Three independent live runs
> producing the identical qualitative outcome (same repos succeed, same repos hit the
> payload limit, same zero effect on pass_rate) puts this well past "might be a fluke" —
> it's a stable, reproducible property of this specific model/retrieval/corpus
> combination, not noise.

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0006 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0012 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
