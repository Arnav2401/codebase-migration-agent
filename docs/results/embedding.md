# Eval results — `embedding`

> **Caveat 1 — same quota wall as every Gemini arm.** All 7 repos hit the 429 wall on
> repair (docs/decisions.md D48) except `eyurtsev__kor`, correctly skipped as
> all-preexisting (D37). T1-only-shaped result below, same numbers as
> `graph`/`wholefile`/`t1_only`.
>
> **Caveat 2 — a real, separate bug this arm's own live run surfaced: `embedding` cannot
> run with `max_workers>1` today.** Two attempts at `--max-workers 4` both crashed
> silently mid-run — the log dies immediately after `SentenceTransformer` weight-loading
> output with zero repos scored, no `harness.repo_failed`/exception, nothing; `ps aux`
> confirmed the process itself was gone, not hung. A `--max-workers 1` retry (this run)
> completed cleanly end to end. The likely cause: `EmbeddingRetrieval`/
> `SentenceTransformerEmbedder` (`agent/retrieval.py`) constructs a fresh
> `SentenceTransformer` instance lazily, per repo, inside whichever worker thread first
> calls `.embed()` — four threads doing that concurrently is very likely hitting a
> PyTorch/`sentence-transformers` thread-safety issue or HuggingFace cache file
> contention (multiple threads reading/writing the same cached model files at once), not
> anything in this project's own D66 parallelism code, which the other six arms ran under
> `--max-workers 4` without incident. Not fixed at the time this run was recorded — it
> just documented the limitation and used `--max-workers 1` to get a real result instead.
>
> **Fixed since, docs/decisions.md D67, and confirmed live 2026-09-04:** one shared
> `SentenceTransformerEmbedder` instance per `run_corpus` call (instead of one per repo),
> guarded by a per-instance lock around its whole `embed()` body — see D67 for the full
> writeup and its two concurrency regression tests. A live `--max-workers 4` re-run of
> this exact arm/split afterward completed cleanly: all 7 repos scored, exit code 0, no
> `harness.repo_failed`, and — the direct proof — the `Loading weights` progress bar
> appeared exactly ONCE in the whole log even though four repos' repair() calls fired
> within the same ~3-second window, confirming the model loads once and is shared rather
> than raced per worker thread. The table below is still the original `--max-workers 1`
> run, not that re-run's numbers — per-repo pass rates shift between live attempts purely
> from Gemini 429 quota state at run-time (caveat 1), so the re-run wasn't promoted to a
> new canonical table; it exists solely to confirm the crash is gone.
>
> **Re-run again 2026-09-04 (part of this session's later quota-refresh retry cycle
> across arms) — D67's fix still holds, but quota-blocked this attempt.** `--max-workers
> 4`, `sentence-transformers` genuinely installed (not just the ImportError path):
> exit code 0, all 7 repos scored, no `harness.repo_failed`, and `Loading weights` logged
> exactly ONCE again even though four repos (`SupImDos__pydantic-argparse`,
> `madkote__fastapi-plugins`, `iscc__iscc-core`, `Aiven-Open__rohmu`) hit repair within
> the same ~3-second window — the concurrency fix keeps holding under repeated live
> exercise, not just the first two verification runs. Every repo needing repair hit an
> immediate 429 this time, unlike the second verification run above which got real
> repair traffic through — this arm shares the rest of this session's finding that
> outcome depends on quota timing, not on anything wrong with the fix. Numbers below are
> the T1-only-shaped degenerate result, byte-identical to `t1_only`.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00

No confidence interval below — this table reports one arm in isolation. Bootstrap 95% CIs are computed when combining arms into `main.md` (`write_main_report`, a separate step over every arm's own repos).

| repo_id | pass_rate | full_green | usd_spent | iterations |
|---|---|---|---|---|
| Aiven-Open__rohmu | 0.000 | False | 0.0000 | 1 |
| SupImDos__pydantic-argparse | 0.000 | False | 0.0000 | 1 |
| cmudig__draco2 | 0.884 | False | 0.0000 | 1 |
| eyurtsev__kor | 0.955 | False | 0.0000 | 1 |
| iscc__iscc-core | 0.000 | False | 0.0000 | 1 |
| madkote__fastapi-plugins | 0.000 | False | 0.0000 | 1 |
| okfn__opendataeditor | 0.022 | False | 0.0000 | 1 |
