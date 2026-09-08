# Phase 6 — Audit trace and PR workflow

**Est. 1 week. Locked until `docs/results/main.md` has real numbers.**

## Why this exists

The trace gets you three things from one piece of work: debuggability while building,
observability to demo, and — most importantly — the guarantee that every number you report
is reconstructible (invariant I6). The PR workflow shows you think about deployment rather
than demos.

## 6a. Trace

Structured events (interfaces.md §7) written as JSONL per run, indexed in SQLite.
Every LLM call, tool call, patch, test run, and triage decision. Tokens and USD on every
LLM event.

**Requirement: a run can be replayed from its trace.** Build `pmigrate replay <run_id>`
that reconstructs the state timeline and prints the decision sequence. If you can't replay
it, the trace is incomplete.

Redaction: no API keys, no absolute paths containing your username, no full repo contents
(store a content hash and a pointer to the on-disk log instead).

**Dashboard** — small FastAPI + HTMX or Streamlit page: run list, per-run timeline, cost
breakdown, failure-class distribution, diff viewer. Two days maximum. It exists because a
screenshot in the README does more recruiting work than the code, not because you need it.

## 6b. PR workflow

- **Fork first. Never open a PR against a repo you don't own (I7).** Hardcode an org
  allowlist. Opening unsolicited AI-generated PRs against real projects is rude, gets you
  blocked, and would be a genuinely bad look on a portfolio project.
- Branch `pmigrate/pydantic-v2-<run_id>`, commits split **by migration unit** so the history
  reads like a human's.
- PR body generated from the trace:
  - what changed, grouped by unit, with the codemod rule ids that fired
  - *why*, for the non-mechanical changes
  - test results before → after
  - failure classes encountered and how each was resolved
  - **confidence score** and what drove it
  - cost and iteration count (a nice honest touch few projects include)
- **Draft PRs only.** Low-confidence runs get a `needs-human-review` label and an explicit
  list of the flagged diffs.

**Confidence score** — define it, don't hand-wave it. A defensible formula:

```
confidence = w1 * (fraction of changed lines from `mechanical` codemods)
           + w2 * (1 - normalized iterations-to-green)
           + w3 * (1 - fraction of diagnoses in the hard classes)
           + w4 * (test coverage of the changed symbols, if measurable)
```

Calibrate the weights on the dev split — then **report calibration**: bucket runs by
predicted confidence and show actual pass rate per bucket. A calibration plot is a
disproportionately strong signal that you know what you're doing.

## Acceptance criteria

- [x] `pmigrate replay <run_id>` reconstructs a full run from its trace alone (D90/D91)
- [~] Every scored eval run has a trace (D91 — `trace_path` recorded on every `RepoResult`,
  verified on a live dev run). Cost accounting is emitted per `llm_call` and replay reports
  a LOWER BOUND when any call lacks a price, but has NOT yet been reconciled against a
  provider invoice.
- [~] Dashboard shows runs, timeline, cost, failure classes (D95,
  `docs/results/dashboard.html`, `pmigrate dashboard`) — built over a SQLite index of the
  traces. The diff viewer is NOT built: 6a forbids storing repo contents in a trace, so
  the diff text does not exist to render. The page states that rather than relaxing the
  redaction rule.
- [~] A real draft PR opened on your own fork of a corpus repo, body generated from the
  trace — the body generator and the I7 fork-only guard are built, tested and dry-run
  against a real trace (D94, `/tmp/pr_body.md`). NO PR has been opened: pushing to
  GitHub is an outward-facing action and is left for an explicit go-ahead.
- [x] Confidence score defined, calibrated, and its calibration plotted (D92,
  `docs/results/calibration.md`). The plot's finding is that the score RANKS but is
  over-confident (+0.50 in the top bucket); weights were deliberately not fitted to the
  dev split while 55% of the formula's inputs remain unmeasurable.
