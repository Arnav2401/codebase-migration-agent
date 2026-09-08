# Eval results — `graph`

> **FINAL HELD-OUT NUMBER: 0.028. Test-split run 3 of 3 — the I5 budget is now exhausted
> (docs/decisions.md D87).** Unchanged from run 1, and **uninformative**: zero repairs
> executed. `lnbits__lnurl` built its prompt (5294 tokens, 4 files) and then hit a 429
> because the five-arm dev sweep immediately beforehand had drained Groq's budget;
> `isaacharrisholt__quiffen` returned `repair_no_target` — `extract_target_file` cannot find
> a target in that repo's failure shape, which is a real product gap, not infrastructure.
>
> **So this measures T1 alone, exactly as runs 1 and 2 did.** Dev is now 0.542 with repair
> working (D85/D86), and whether that generalizes to unseen repos is **unmeasured, and
> unmeasurable** without a new split or an I5 amendment.
>
> Spending the last permitted run on a window where the system could not demonstrate
> anything was a sequencing error — dev sweep first, quota check, *then* the held-out run.
> Recorded rather than quietly re-run, because re-running is precisely what I5 forbids.

**2 repos** — 0 full green (every seed passed), mean pass rate 0.028, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.100 [0.021, 0.178] (n=2/2) line jaccard, 0.718 [0.636, 0.800] (n=2/2) symbol precision, 0.218 [0.103, 0.333] (n=2/2) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| isaacharrisholt__quiffen | 0.000 | False | 0.0000 | 2 | 0.178 | 0.636 | 0.333 |
| lnbits__lnurl | 0.056 | False | 0.0000 | 1 | 0.021 | 0.800 | 0.103 |
