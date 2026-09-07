# Eval results — `t1_only`

> **The reference row, and on this round's evidence the arm doing all the real work.**
> Never calls a model (D62), so its $0.00 is correct by design and its results are fully
> deterministic. Dev split, k=1.
>
> **Both arms that genuinely exercised LLM repair this round — `graph` (4 patches, NVIDIA)
> and `model_groq` (20 patches, Groq) — landed on this arm's exact mean of 0.396**
> (docs/decisions.md D78). The codemods account for the entire measurable result on this
> corpus; 24 applied LLM patches across two providers added nothing on top of it.
>
> What T1 alone does, per repo: `iscc__iscc-core` 0.000 → **1.000**, full green, the
> cleanest win in the corpus. `eyurtsev__kor` 0.955 → **0.506** — T1 actively BREAKS this
> repo (compare `no_t1`, which leaves it untouched at 0.955), and no repair arm recovered
> it this round. `cmudig__draco2` 0.884 → 0.878, marginally worse.
>
> Caution: `embedding`, `no_triage` and `wholefile` also report 0.396 here, but for a
> different reason — their repair calls were all 429'd, so they measured T1 and nothing
> else. Identical numbers, three different causes.

**7 repos** — 1 full green (every seed passed), mean pass rate 0.396, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.216 [0.075, 0.376] (n=7/7) line jaccard, 0.541 [0.330, 0.755] (n=7/7) symbol precision, 0.616 [0.380, 0.813] (n=7/7) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 | 0.009 | 0.241 | 0.778 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 | 0.000 | 0.250 | 0.037 |
| cmudig__draco2 | 0.878 | False | 0.0000 | 1 | 0.464 | 0.778 | 0.636 |
| eyurtsev__kor | 0.506 | False | 0.0000 | 1 | 0.197 | 0.533 | 0.727 |
| iscc__iscc-core | 1.000 | True | 0.0000 | 1 | 0.059 | 0.250 | 1.000 |
| madkote__fastapi-plugins | 0.370 | False | 0.0000 | 1 | 0.549 | 0.732 | 0.769 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 | 0.233 | 1.000 | 0.364 |
