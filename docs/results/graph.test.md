# Eval results — `graph`

> **THE HELD-OUT NUMBER. Test-split run 1 of at most 3 ever permitted (I5/D7),
> 2026-09-08.** phase-5-eval.md: "Test split run once, at the end, and the number is
> whatever it is." It is **0.028**.
>
> Both repos were discovered, validated and baselined (D82) only after every dev-split
> result in this project had been collected, so nothing was tuned against them. Groq
> `openai/gpt-oss-120b`, `graph` arm, k=1, D75 prompt cap, $0.0032 spent, 1 repair applied,
> 1 failed, 1 `repair_no_target`.
>
> **Dev said 0.396. Held-out says 0.028.** That gap is the single most important number
> this project has produced, and it is not noise: dev's 0.396 leans almost entirely on
> `iscc__iscc-core` going full green under T1's codemods, plus partial credit on two other
> repos the codemods happen to suit. On two repos nobody tuned against, the same pipeline
> recovers 5.6% of `lnbits__lnurl`'s suite and 0% of `isaacharrisholt__quiffen`'s.
>
> Read it as an upper bound on nothing and a lower bound on nothing — N=2. What it does
> establish is direction: the dev number is optimistic about unseen code, which is exactly
> what a held-out split exists to reveal, and exactly why relabelling tuned-against dev
> repos as "test" (rejected in D79) would have hidden it.
>
> Consistent with D78: the repair tier applied 1 patch here and the outcome still tracks
> what T1 alone would do.

**2 repos** — 0 full green (every seed passed), mean pass rate 0.028, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

Diff-similarity (docs/phase-5-eval.md): 0.109 [0.040, 0.178] (n=2/2) line jaccard, 0.739 [0.636, 0.842] (n=2/2) symbol precision, 0.236 [0.138, 0.333] (n=2/2) symbol recall. `—` per repo below means not measured (no human ground-truth diff, or neither side touched a Python file), not a real 0.0.

| repo_id | pass_rate | full_green | usd_spent | iterations | diff_line_jaccard | symbol_precision | symbol_recall |
|---|---|---|---|---|---|---|---|
| isaacharrisholt__quiffen | 0.000 | False | 0.0000 | 2 | 0.178 | 0.636 | 0.333 |
| lnbits__lnurl | 0.056 | False | 0.0032 | 2 | 0.040 | 0.842 | 0.138 |
