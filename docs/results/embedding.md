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
> `--max-workers 4` without incident. Not fixed here — this run just documents the
> limitation and uses `--max-workers 1` to get a real result instead. A real fix (e.g.
> one shared, lazily-built model instance instead of one per thread, or a lock around
> construction) is a genuine, separate follow-up.

**7 repos** — 0 full green, mean pass rate 0.266, total cost $0.00 (T1-only; run sequentially, see caveats above)

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
