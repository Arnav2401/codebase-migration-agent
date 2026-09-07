# Eval results — main

Bootstrap 95% CIs (docs/decisions.md D65): 10000 resamples, seed=0, resampling REPOS within each arm — not a normal-approximation interval, since a few dozen repos is a small, plausibly non-normal sample. A narrow N means a wide interval; that width is reported here rather than hidden. N is the number of distinct repos, not repo x seed cells, even for an arm run under multiple seeds (docs/decisions.md D72).

| arm | N | pass_rate (mean [95% CI]) | full_green (fraction [95% CI]) | mean cost | line_jaccard (mean [95% CI], n measured) | symbol_precision (mean [95% CI], n measured) | symbol_recall (mean [95% CI], n measured) |
|---|---|---|---|---|---|---|---|
| embedding | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| graph | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.03 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| model_groq | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| no_t1 | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| no_triage | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| t1_only | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |
| wholefile | 7 | 0.266 [0.003, 0.549] | 0.000 [0.000, 0.000] | $0.00 | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) | 0.000 [0.000, 0.000] (n=7/7) |

## Per-repo appendix

### embedding

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### graph

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0963 | 1.3 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 [0.884, 0.884] (k=3 seeds) | 0/3 | 0.0176 | 1.7 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 [0.955, 0.955] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 [0.000, 0.000] (k=3 seeds) | 0/3 | 0.0000 | 1.0 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 [0.022, 0.022] (k=3 seeds) | 0/3 | 0.0986 | 1.3 | 0.000 | 0.000 | 0.000 |

### model_groq

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0006 | 2 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0011 | 2 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### no_t1

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### no_triage

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 2 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### t1_only

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |

### wholefile

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
