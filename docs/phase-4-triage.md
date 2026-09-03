# Phase 4 — Failure triage

**Est. 1.5 weeks. This is where you add engineering the model can't do for you.**

## Why this exists

The naive loop dumps a 4000-line pytest log into the context window and hopes. That fails
three ways: it's expensive, it buries the signal, and it gives the model no idea *what kind
of problem* it's looking at — so it applies a generic fix to a specific failure.

Instead: parse the failure, classify it against a known taxonomy, group failures that share
a root cause, and route each group to a strategy with its own prompt, its own retrieval
query, and its own **allowed edit surface**.

> Interview answer: "A dependency version conflict and a coercion-semantics change are
> completely different problems that happen to both look like a red test. Classifying them
> lets me give the third-party case a strategy that can only edit the dependency file — so
> the model can't 'fix' a version conflict by rewriting my models."

## The taxonomy

See `FailureClass` in interfaces.md §6. The classes, with their pydantic-v2 specifics:

| Class | Signature in the log | Strategy |
|---|---|---|
| `IMPORT_ERROR` | `ImportError: cannot import name 'BaseSettings'`, `PydanticImportError`, collection errors | Import fix; often a T1 rule that was missed. Allowed: the importing module + deps file. |
| `CLASS_DEF_ERROR` | `PydanticUserError` at import: "validator must be a classmethod", unrecognised config key, `@validator` on a missing field | Fix the class definition. Retrieval: the class + its bases. |
| `REMOVED_API` | `AttributeError: 'X' object has no attribute 'dict'`, `__fields__`, `parse_obj` | Mechanical — re-run the relevant codemod on the file the traceback points to. Often needs no LLM at all. |
| `VALIDATION_BEHAVIOUR` | `ValidationError` where v1 passed: str→int coercion now rejected, implicit-Optional, `strict` differences | The hard class. Needs T2 with full symbol neighbourhood. |
| `SERIALIZATION_DIFF` | assertion on `.model_dump()` output shape, `exclude_unset`, datetime/Decimal formatting | T2, retrieval = the model + the asserting test (read-only). |
| `ERROR_MESSAGE_DIFF` | test asserts on v1 error strings/`ValidationError` structure | **Tricky and important**: the test is asserting on behaviour that legitimately changed. The agent may not edit the test (I1). Correct outcome is often "flag for human review" — record it rather than forcing a fix. |
| `THIRD_PARTY_PIN` | fastapi/sqlmodel/inference-lib incompatibility | Allowed paths: **dependency files only**. |
| `PREEXISTING` | node id ∈ `baseline.failed` | Ignore entirely (I4). |
| `FLAKY` | passes on rerun | Rerun once, then exclude and log. |
| `UNKNOWN` | anything else | LLM classifier fallback; every `UNKNOWN` you see is a candidate new rule. |

## Implementation

**Rule-first, LLM-last.** Classification is regex + traceback frame parsing + a lookup of
the failing frames' file/line into the Phase 1 graph to get `suspect_symbols`. Only
unmatched failures go to an LLM classifier. This keeps triage deterministic, testable,
and nearly free — which is the entire argument for building it.

**Grouping matters as much as classification.** Twenty tests failing from one bad import is
*one* problem. Group by (class, root traceback frame) before routing, and fix once.

**Build the labelled set as you go.** Every run's failures, with your hand-assigned correct
class, go into `tests/fixtures/triage/`. That's your classifier's test set — and reporting
classifier accuracy on it is a free extra metric.

## Acceptance criteria

- [x] Classifier accuracy ≥85% on a hand-labelled set of ≥100 real failures from Phase 3 runs
      — **96.8%** (398/411, `tests/fixtures/triage/labelled_dev.jsonl`), continuously
      checked by `tests/eval/test_classifier_regression.py`. Full trace, including the
      raw-72.5%-to-96.8% path and two accepted residual gaps: docs/decisions.md D55/D56.
- [x] Failures grouped by root cause — measured as average failures-per-diagnosis > 1
      — confirmed (~14-15 average across both `use_triage` arms on the Gemini run).
      docs/results/triage.md, docs/decisions.md D51.
- [x] **Measured pass-rate lift vs. Phase 3 on the dev split, same model, same seed.**
      This is the phase's whole justification. If the lift is small, say so honestly and
      investigate why — that's a better interview story than a fabricated win.
      — 0.6672 (ON) vs 0.5771 (OFF) on the 6 same-model-comparable repos (Groq,
      `openai/gpt-oss-120b`), docs/results/triage.md's headline table. Not a large lift on
      every repo — read the per-repo breakdown, not just the average.
- [x] Median cost per repo drops (fewer tokens, targeted context)
      — $0.0016 (ON) vs $0.0022 (OFF) median usd/repo. Reported alongside the mean, which
      moves the other way (driven by one hard-case repo's real repair attempts) — see
      docs/results/triage.md's "Median cost per repo drops — but the mean doesn't" section
      for why both numbers matter here.
- [x] Per-class fix-success table generated into `docs/results/triage.md`
      — real, automated (`eval/metrics.py`'s `fix_success_table`, D51/D52), not hand
      reconstructed. `unknown` class: 55% fix rate on 14 real attempts.

That last table is the single most valuable artefact in the project for interviews.

**Known gaps carried forward, not blocking the phase:** a same-model `use_triage=True` vs
`False` fix-success-table comparison (Gemini's OFF arm hit its daily quota wall before any
real attempt; Groq's own equivalent needs a clean run once its quota resets); two
documented, deliberately-unfixed classifier gaps (D56) that would need genuinely new
evidence, not overfit regexes, to close.
