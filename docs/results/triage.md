# Phase 4 results: does triage-routed repair actually help?

**Run date:** 2026-09-03. **Model backend:** Groq `openai/gpt-oss-120b` (docs/decisions.md
D48/D49 — Gemini's free tier turned out to trickle-refill rather than reset daily,
impractical for a real run; Groq's key measured 1000 req/min of headroom). **Corpus:** 5
repos, `corpus/manifest.json`, dev split. **Budget:** `usd_cap=1.0`, `max_iterations=8`
per repo. **Code state:** every fix from D40 through D49 applied — this is the first run
where the harness, sandbox overlay, and scoring were all simultaneously correct.

This is a small corpus (5 repos) run once per arm — real numbers, not a statistically
robust study. Treat the comparison as a first, honest signal, not a final verdict.

## Headline comparison: `use_triage=True` vs `use_triage=False`

`use_triage` (docs/decisions.md D40) is the one ablation axis built so far: with it off,
`repair()` falls back to the pre-D38 shape — every raw failure dumped into one prompt,
no per-class routing, no PREEXISTING skip in `route()`.

| Repo | pass_rate (ON) | pass_rate (OFF) | usd (ON) | usd (OFF) | What happened |
|---|---|---|---|---|---|
| `madkote__fastapi-plugins` | 0.37 | **0.52** | $0.0000 | $0.0023 | OFF did better — ON's diagnosis-routed target had a traceback shape `extract_target_file` couldn't match, so repair was never attempted at all (`repair_no_target`); OFF's combined-failure prompt found a fixable target elsewhere |
| `SupImDos__pydantic-argparse` | 0.00 | 0.00 | $0.0060 | $0.0081 | Genuinely hard case either way — `pydantic.fields.ModelField` has no 1:1 v2 equivalent. 8-9 real repair attempts per arm, all honest failures, not a harness bug (confirmed via D46's canary test) |
| `Aiven-Open__rohmu` | 0.87 | 0.86 | $0.0040 | $0.0026 | Nearly identical — both arms found and applied the same real fix (`@root_validator` → `@model_validator` shape, `CLASS_DEF_ERROR`) |
| `iscc__iscc-core` | **1.00** | 1.00 | $0.0000 | $0.0000 | No repair needed either way — T1 alone resolves it (confirmed identically across every run this session, with and without a model client at all) |
| `eyurtsev__kor` | **0.96** | 0.51 | $0.0012 | $0.0000 | ON did much better — OFF hit `413 Payload Too Large` (all diagnoses' raw text combined exceeded Groq's request size limit) and never got to attempt repair at all |

**Average pass rate: 0.640 (ON) vs 0.578 (OFF).** Total cost across both arms: **$0.0237**.

## Why triage wins, in the two cases where it clearly did

Both `kor`'s win and the `413` failures share one root cause: `use_triage=False` builds
its prompt from `collect_failure_texts()`, which concatenates *every* raw failure's full
text into a single prompt — for a repo with several genuinely different problems (or many
copies of the same problem across files), that blob can be large enough to hit a request
size limit before the model ever sees it. `use_triage=True` picks exactly one
`GroupedDiagnosis` (`agent/graph.py`'s `_REPAIR_PRIORITY`) and sends only *that*
diagnosis's raw failures — smaller by construction, and focused on one fixable problem
instead of asking the model to somehow address everything at once. This is the argument
`docs/phase-4-triage.md` makes for why triage should matter, now backed by a real number
instead of an assertion.

## Where it didn't win: `madkote__fastapi-plugins`

Worth reporting honestly rather than only citing the wins. The ON arm's diagnosis for
this repo happened to point at a failure whose traceback shape `extract_target_file`
(`agent/repair.py`) doesn't handle — a real, narrow gap in that heuristic, not a triage
design flaw — so `repair()` gave up before ever calling the model. The OFF arm's combined
prompt, containing the SAME underlying failures plus others, happened to give the model
enough surrounding context to find and fix a different, real target. This is a genuine
edge case, not evidence that per-diagnosis routing is generally worse — it's a concrete,
reproducible bug report against `extract_target_file`'s traceback-frame matching, worth
fixing on its own.

## Preliminary per-class attempt tally (`use_triage=True` arm only)

Not the full fix-success table `docs/phase-4-triage.md` asks for — that needs `AgentState`
to retain repair-attempt/run history it doesn't have yet (flagged as future work in D40).
This is a hand-reconstruction from this run's own structlog events (`agent.repair_applied`
now carries `cls`/`strategy` per D38 specifically so this becomes possible), with a tiny
sample size — read it as "what happened in these 12 real attempts," not a rate.

| Class | Attempts | Outcome |
|---|---|---|
| `class_def_error` | 1 | Fixed — `rohmu` went from fully blocked (0/195) to 170/195 in one call |
| `unknown` | 8 | 1 fixed (`kor`'s `parser.py`, collection unblocked + 40 more tests passing), 7 not fixed (`pydantic-argparse`'s hard case, 6 attempts + `rohmu`'s second-pass attempt with an inconclusive result — the narrow re-test covered different node_ids than the ones this attempt could have affected) |
| `import_error` | 1 | Not fixed (`pydantic-argparse`) |
| `validation_behaviour` | 1 | Inconclusive — applied against `rohmu`'s already-fixed `config.py`; the next test run's narrow selection didn't cover any node_id this specific edit could have changed |

## What's NOT here yet

- **Classifier accuracy on a hand-labelled set.** `docs/results/triage_failures_dev.jsonl`
  now has 78 real residual failures with predicted classes and full traceback text from
  this run alone (overwritten each run, not yet accumulated) — real seed data, but still
  short of `phase-4-triage.md`'s ≥100 target, and nothing has been hand-labelled against
  it yet.
- **A full, statistically meaningful per-class fix-success table.** Needs both a bigger
  corpus (5 repos gives too few samples per class) and the `AgentState` repair-attempt-
  history extension flagged in D40.
- **Multiple seeds/reruns for variance.** This is one run per arm; `Aiven-Open__rohmu`'s
  87% vs 86% is close enough that a second run could plausibly flip which arm "wins" on
  that repo specifically — the `kor` and `madkote` results are large enough deltas to be
  more likely durable, but that's an assumption, not something re-verified here.

## Raw data

- Per-repo scores (JSON): `corpus_run_groq_results.json` (scratch — not committed;
  regenerate via `scratchpad/run_corpus_groq.py` if needed)
- Residual failures with full text: `docs/results/triage_failures_dev.jsonl`
- Full run logs with every `agent.*` event: session-local, not retained past this run
