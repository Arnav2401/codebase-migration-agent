# Eval results — `wholefile`

> **Re-run 2026-09-04 (fourth attempt) — first real signal this arm has ever gotten.**
> 6 of 7 repos hit Gemini's 429 wall (`SupImDos__pydantic-argparse`, `iscc__iscc-core`,
> `Aiven-Open__rohmu`, `cmudig__draco2`, `okfn__opendataeditor` on repair;
> `eyurtsev__kor` correctly skipped, D37). But `madkote__fastapi-plugins` got a genuine
> `agent.repair_applied` this time (`fix_import`, two files rewritten,
> `fastapi_plugins/plugin.py` and `demo.py`, real cost $0.037) — mechanically accepted
> (`violations=[]`), but `pass_rate` stayed 0.0 after a second `run_tests` iteration:
> same "repair applies cleanly, doesn't fix the test" pattern already seen independently
> in `graph`'s and `model_groq`'s own real repairs. Three prior attempts at this arm
> never got a single repair call through at all; this is the first one that did. Still
> 0 full green, but no longer purely a quota story for `wholefile` specifically — the
> wholefile-vs-graph-vs-embedding ablation still can't be drawn from this (most repos
> here still never got a clean attempt), but the arm itself is no longer untested.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.04 (first real repair
attempt through on this arm, still quota-blocked for the rest — see caveat above)

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0367 | 2 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
