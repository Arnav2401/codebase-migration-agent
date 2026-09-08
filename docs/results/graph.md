# Eval results — `graph`

> **The repair tier finally contributes (docs/decisions.md D85/D86).** Dev split, k=1,
> Groq `openai/gpt-oss-120b`, prompt cap 6000 tokens. **Mean 0.5422 against `t1_only`'s
> 0.3965** — re-measured under the identical configuration, so this is a like-for-like
> comparison, not a mixed-config artifact (D77). 8 repairs applied.
>
> Every earlier round had this arm landing on exactly the codemod baseline (D78, and D84
> held-out). Two fixes changed it:
> - The prompt never told the model what pydantic v2 **removed**. It was "fixing"
>   `pydantic.fields.ModelField` — deleted in v2 — by renaming how it referenced the dead
>   symbol. It now carries a removed-vs-renamed table and the four cases T1 explicitly
>   flags for T2.
> - Repair saw one file per iteration on an import chain 8 files deep, so `pass_rate`
>   could not move until the whole chain was fixed (one collection error means pytest
>   collects nothing). It now gets the chain from the traceback.
>
> Per-repo: `Aiven-Open__rohmu` **0.000 → 0.8718**, pinned at zero for the entire project
> until now. `madkote__fastapi-plugins` 0.370 → 0.5185. `SupImDos__pydantic-argparse` and
> `okfn__opendataeditor` are unchanged, so this is not uniform improvement.
>
> 20 rate-limit retries were absorbed rather than failing the attempt — D86: Groq reports
> a tokens-per-minute overage as `413 Payload Too Large`, which was being treated as fatal
> and was killing half the repair attempts.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.542, total cost $0.01

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.093 [0.005, 0.253] (n=7/7) line jaccard, 0.234 [0.071, 0.433] (n=7/7) symbol precision, 0.410 [0.114, 0.735] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.872 | False | 0.0031 | 2 | 0.018 | 0.267 | 0.889 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0057 | 3 | 0.018 | 0.385 | 0.185 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.519 | False | 0.0020 | 3 | 0.560 | 0.738 | 0.795 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.000 | 0.000 | 0.000 |
