# Eval results — `model_groq`

> **Re-run 2026-09-04 (fourth live attempt) — reproduces the same finding a fourth
> consecutive time.** Same 4 repos (`madkote__fastapi-plugins`, `iscc__iscc-core`,
> `Aiven-Open__rohmu`, `okfn__opendataeditor`) hit Groq's `413 Payload Too Large` limit;
> `eyurtsev__kor` again correctly skips repair (`preexisting`, D37).
> `SupImDos__pydantic-argparse` got a real `agent.repair_applied` (`missing_t1_rule`) and
> stayed at 0.0 — fourth time running. `cmudig__draco2` got a real `agent.repair_applied`
> (`fix_class_def`) and landed at the same 0.884 T1-only baseline — fourth time running.
> Costs stay in the same tiny range across all four attempts (SupImDos ~$0.0005–0.0008,
> cmudig__draco2 ~$0.0011–0.0012). Four independent live runs, identical qualitative
> result every time: this is as settled a finding as this session has produced for any
> arm — this specific model/retrieval/corpus combination reliably gets two mechanically
> clean repairs through and reliably has them fix nothing.

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0008 | 2 |
| cmudig__draco2 | 0.884 | False | 0.0012 | 2 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
