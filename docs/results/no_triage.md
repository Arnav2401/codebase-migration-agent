# Eval results — `no_triage`

> **Re-run 2026-09-04 (third attempt) — genuinely re-attempted (stale cache cleared
> first), same quota wall, same real finding reproduces a third time.** 6 of 7 repos hit
> Gemini's 429 wall immediately. `eyurtsev__kor` again gets the distinct `triage=False`
> code path: D37's all-preexisting skip is disabled, repair genuinely fires
> (`iterations=2`) and hits `agent.repair_no_target` — identical outcome to both prior
> runs. Three consecutive independent runs producing the exact same
> `repair_no_target` result removes any doubt this is a reliable behavior of the
> `use_triage=False` path on this specific repo, not noise. Numbers otherwise
> byte-identical to every prior attempt and to `wholefile`/`no_t1`'s own re-runs today
> (see their notes) — this arm shares the same "hasn't landed inside the quota window"
> problem.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (quota-blocked again
except eyurtsev__kor's third confirmed no-target attempt, see caveat above)

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 2 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
