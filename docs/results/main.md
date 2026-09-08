# Eval results — main

> **The repair tier now adds measurable value (docs/decisions.md D85/D86).** Dev split,
> k=1, matched configuration: `graph` **0.5422** vs `t1_only` **0.3965** — +0.146 absolute,
> +37% relative. Every prior round in this project had the two arms identical (D78), and
> the held-out run (D84) showed the same. That is no longer true.
>
> What changed: the repair prompt was given the v1→v2 API knowledge it never had (it had
> been "fixing" symbols pydantic *deleted* by renaming how it referenced them), and repair
> now receives the whole import chain from the traceback instead of one file per iteration.
> Separately, Groq's `413 Payload Too Large` turned out to be a tokens-per-minute rate
> limit whose body said so — it was being treated as fatal and killing half the attempts.
>
> Only `graph` and `t1_only` appear below: changing the prompt cap changed every arm's
> `config_hash`, and D77 correctly refuses to mix configurations under one arm name. The
> other five arms need re-running before they can be compared, and the held-out number
> (0.028, D83/D84) predates all of this — it should be re-measured, but that costs the
> last of the three permitted test-split runs (I5), so it is deliberately not spent here.
>
> Note for whoever regenerates this file: `report_cli` rewrites it, so this caveat is
> hand-maintained. D85/D86 are the durable record.

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden. N is the number of distinct repos, not repo x seed cells, even for an arm run under multiple seeds (docs/decisions.md D72).

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | symbol_recall (mean [95% CI], n measured) |
|---|---|---|---|---|---|---|---|
| graph | 7 | 0.542 [0.259, 0.807] | 0.143 [0.000, 0.429] | $0.00 | 0.093 [0.005, 0.253] (n=7/7) | 0.234 [0.071, 0.443] (n=7/7) | 0.410 [0.114, 0.740] (n=7/7) |
| t1_only | 7 | 0.396 [0.128, 0.697] | 0.143 [0.000, 0.429] | $0.00 | 0.216 [0.075, 0.373] (n=7/7) | 0.541 [0.328, 0.753] (n=7/7) | 0.616 [0.384, 0.817] (n=7/7) |

## Per-repo appendix

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.872 | False | 0.0031 | 2 | 0.018 | 0.267 | 0.889 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0057 | 3 | 0.018 | 0.385 | 0.185 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.519 | False | 0.0020 | 3 | 0.560 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### t1_only

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
