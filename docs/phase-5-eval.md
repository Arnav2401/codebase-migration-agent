# Phase 5 — Evaluation harness and ablations

**Est. 1.5 weeks. After this phase you have the resume bullet.**

## Why this exists

Without this, you have a demo. With it, you have a measurement. It also protects you from
yourself: every prompt tweak gets scored, so you notice the "improvement" that cost you
four points.

## Deliverable

`make eval CONFIG=... SPLIT=dev` runs the full matrix and writes `docs/results/*.md`.

## Design

- **Matrix**: repos × configs. Resumable — completed `(repo, config)` cells are skipped
  (store results in SQLite keyed by `(repo_id, config_hash, corpus_sha)`).
- **Parallel** over Docker with a concurrency cap that matches your machine. Cost cap
  enforced globally, not just per repo.
- **Run manifest** per invocation (I6): corpus sha256, prompt hashes, model ids and dates,
  seeds, temperature, config, git sha of the agent, start/end time. Written before the run.
- **Deterministic where possible**: temperature 0, fixed seeds, `-p no:randomly`. Accept
  that LLM sampling still varies — that's why you run k=3 seeds on the dev split and report
  variance rather than pretending it's deterministic.

## The ablation arms (this is the point of the phase)

Each varies exactly one thing:

| Arm | Varies | Answers |
|---|---|---|
| `graph` (baseline) | — | The headline number |
| `embedding` | retrieval = embedding over code chunks | **Does the graph actually help?** ← the resume claim |
| `wholefile` | retrieval = dump every pydantic-touching file, truncate to budget | Is retrieval needed at all, or does a big context window solve it? |
| `t1_only` | no LLM, codemods only | How much of this is just a codemod? |
| `no_t1` | LLM only, no codemods | What are the codemods buying? |
| `no_triage` | Phase 3 triage stub | Phase 4's justification |
| `model_*` | Claude / GPT / local Llama | Cost/accuracy/latency frontier |

The `wholefile` arm is the one a sharp interviewer will ask for and most students don't run.
Run it. If a naive whole-file dump ties your graph retrieval, that is a real finding and you
need to know it before someone else points it out.

## Metrics implementation (`eval/metrics.py`)

**Pass rate** — over `baseline.passed` only (I4). Report both "fraction of tests passing"
and "fraction of repos fully green"; they tell different stories.

**Diff similarity** — two measures, because line-level alone is misleading:
1. Line-level Jaccard over changed lines, whitespace- and format-normalized (run both diffs
   through `ruff format` first, or you're measuring formatting).
2. **Symbol-level precision/recall** — map both diffs to changed symbols via the Phase 1
   graph. "Of the symbols the human changed, what fraction did the agent also change?"
   This is far more meaningful than line overlap and it reuses your own infrastructure,
   which is a nice thing to point out.

Report both; explain that a *low* line-similarity with *high* symbol-recall and green tests
means the agent found a different valid solution — which is fine, and worth saying.

**Cost** — from the trace, using a committed price table. Median and p95.

**Statistics** — bootstrap 95% CIs over repos. With N≈34 the interval is roughly ±15 points;
state it. Publish the full per-repo table so nobody has to trust the aggregate.

## Acceptance criteria

- [ ] Full dev-split run reproduces to within seed variance across two invocations
- [ ] All seven arms run and produce `docs/results/<arm>.md`
- [ ] `docs/results/main.md` has the headline table with CIs and the per-repo appendix
- [ ] Test split run **once**, at the end, and the number is whatever it is (I5)
- [ ] Total eval cost measured and reported

## After this phase

Rewrite the resume bullet with real numbers. If the result is 48%, the bullet says 48% and
your failure analysis carries the interview. An honest 48% with a good failure table beats
an unverifiable 90% every single time, and interviewers can tell the difference instantly.
