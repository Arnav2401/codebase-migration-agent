# Eval results — `model_groq`

> **Re-run 2026-09-05, fifth live attempt — reproduces the same finding a fifth
> consecutive time.** Run immediately after D70's clone-cache fix and the full-matrix
> re-run of the other five arms; `clone_cache/` was already fully populated, so this
> completed in well under a minute with zero clone traffic. Groq isn't Gemini-quota-
> dependent, so this arm keeps hitting its own real capacity limit instead: the same 4
> of 7 repos (`Aiven-Open__rohmu`, `iscc__iscc-core`, `madkote__fastapi-plugins`,
> `okfn__opendataeditor`) hit `413 Client Error: Payload Too Large` — same repos as all
> four prior attempts. `eyurtsev__kor` again correctly skips repair (`preexisting`, D37).
>
> **The core finding holds a fifth time, unchanged:** `SupImDos__pydantic-argparse` got
> a real `agent.repair_applied` (`missing_t1_rule`) and stayed at `pass_rate=0.0` — fifth
> time running. `cmudig__draco2` got a real `agent.repair_applied` (`fix_class_def`) and
> landed at the same `0.884` T1-only baseline — fifth time running. Costs stay in the
> same tiny range (`SupImDos` ~$0.0006, `cmudig__draco2` ~$0.0011). Five independent live
> runs now, identical qualitative result every time — this finding is as settled as
> anything in this project gets.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0006 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0011 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
