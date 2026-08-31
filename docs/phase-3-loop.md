# Phase 3 — The migration loop

**Est. 2 weeks. End-to-end green on ONE repo is the bar. Not two, not the corpus. One.**

## Why this shape

The loop is a state machine because the control flow is genuinely stateful: you need
checkpointing (resume a run after a crash), budget enforcement at every node, and a trace
of exactly which transition happened. LangGraph gives that structure. A while-loop with
if-statements gives you a demo you can't debug.

## The graph

```
        ┌──────┐
        │ plan │  work_list() from Phase 1 → ordered batches of MigrationUnits
        └───┬──┘
            ▼
     ┌─────────────┐
     │ select_unit │◀────────────────────────────┐
     └──────┬──────┘                             │
            ▼                                    │
      ┌──────────┐   T1 codemods, then T2 LLM    │
      │   edit   │   for units with difficulty>1 │
      └─────┬────┘                               │
            ▼                                    │
     ┌──────────────┐  syntax + import check     │
     │   validate   │  (cheap, in-process)       │
     └──────┬───────┘                            │
            ▼                                    │
      ┌────────────┐                             │
      │ run_tests  │                             │
      └─────┬──────┘                             │
            ▼                                    │
       ┌─────────┐  green? next unit ────────────┘
       │ triage  │  red?   → repair
       └────┬────┘  no progress twice? → escalate/abort
            ▼
       ┌─────────┐
       │ repair  │──▶ back to validate
       └─────────┘
            │ all units done and full suite green
            ▼
       ┌──────────┐
       │ finalize │  diff, confidence score, trace flush
       └──────────┘
```

## Node responsibilities

**plan** — call `work_list(graph, repo_id)`. No LLM. The plan comes from the graph, which is
the whole argument for Phase 1. Also apply the global dependency change up front (bump the
pydantic constraint), because nothing else can pass until it's done.

**select_unit** — pop the next batch. Leaves first. SCC members go together.

**edit** — two tiers:
- **T1 codemods** (`codemod/`) run first, unconditionally, on the unit's files. Deterministic,
  free, and they clear the mechanical noise so T2 sees a smaller problem.
- **T2 LLM** runs only if the unit still has `est_difficulty > 1` or T1 flagged
  `needs-review` edits. Context comes from `graph.neighbourhood()`. The model gets the small
  tool set from interfaces.md §5 — **not** free file access.

**validate** — before spending a test run: does every touched file parse? Does the module
import cleanly in a throwaway subprocess? Catches ~half of bad edits at ~0 cost.

**run_tests** — the expensive node. Rate-limited by `budget.py`. Full run at unit boundaries;
selective re-runs during repair.

**triage** — Phase 3 stub: group failures naively and hand the model the trimmed log.
Phase 4 replaces this with the real classifier. Keeping it as a distinct node from day one
is what makes the Phase 4 lift measurable.

**repair** — targeted fix attempt against a diagnosis. Bounded by `max_attempts`.

**finalize** — produce the diff, compute a confidence score, flush the trace.

## Codemod rules to implement (T1)

One file per rule under `codemod/rules/`, each with a `before.py`/`after.py` fixture pair.
Roughly in order of frequency:

| Rule | v1 | v2 | Confidence |
|---|---|---|---|
| `dict_to_model_dump` | `m.dict()` | `m.model_dump()` | mechanical |
| `json_to_model_dump_json` | `m.json()` | `m.model_dump_json()` | mechanical |
| `parse_obj_to_model_validate` | `M.parse_obj(d)` | `M.model_validate(d)` | mechanical |
| `parse_raw_to_validate_json` | `M.parse_raw(s)` | `M.model_validate_json(s)` | likely |
| `config_class_to_configdict` | `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` | mechanical (with a rename map) |
| `validator_to_field_validator` | `@validator("x")` | `@field_validator("x")` + `@classmethod` | likely — signature and `values` → `info.data` |
| `root_validator_to_model_validator` | `@root_validator` | `@model_validator(mode="before"/"after")` | needs-review — mode depends on `pre=` |
| `field_kwargs` | `Field(regex=, min_items=, const=, allow_mutation=)` | `pattern=, min_length=, Literal, frozen=` | mechanical |
| `fields_attr` | `M.__fields__` | `M.model_fields` | mechanical |
| `update_forward_refs` | `M.update_forward_refs()` | `M.model_rebuild()` | mechanical |
| `basesettings_import` | `from pydantic import BaseSettings` | `from pydantic_settings import BaseSettings` + dep add | mechanical |
| `copy_update` | `m.copy(update=...)` | `m.model_copy(update=...)` | likely |
| `implicit_optional_default` | `x: Optional[int]` (implicitly None) | `x: Optional[int] = None` | **needs-review — semantic, this is the classic silent breakage** |
| `custom_validators_protocol` | `__get_validators__` | `__get_pydantic_core_schema__` | needs-review → hand to T2 |
| `json_encoders` | `Config.json_encoders` | field serializers | needs-review → hand to T2 |

`needs-review` rules should **flag, not rewrite** — emit a `RuleEdit` note that routes the
symbol to T2 instead of guessing.

## Anti-cheating (invariants I1–I3)

All enforced in `apply_patch`, the single write chokepoint:
- reject any hunk touching a path matching the test patterns
- reject additions of `pytest.skip`, `pytest.mark.xfail`, `@unittest.skip` anywhere
- reject dependency edits that constrain pydantic below 2
- reject deletions of whole test functions (AST-level check on test files: must be a no-op)

Make the rejection message informative and feed it back to the model — it should learn to
fix the code, not the test.

## Budget guards (`agent/budget.py`)

Checked at *every* node entry: USD per repo, total tokens, iterations, wall clock. On
breach, transition straight to `finalize` with `status="budget_exceeded"` and record it.
A run that costs $40 because it looped is worse than a run that fails at $2.

Add a **no-progress detector**: hash the sorted set of failing node ids; if the same hash
appears twice in a row after a repair, the strategy isn't working — escalate to a different
strategy or abort. This alone saves a large fraction of runaway cost.

## Acceptance criteria

- [ ] One dev-split repo goes from red to fully green with zero human edits
- [ ] The entire run is reconstructible from its trace
- [ ] Budget guard demonstrably aborts a run when capped low
- [ ] Anti-cheat rejects an intentionally test-editing patch
- [ ] T1-only (codemods, no LLM) is runnable as a config — you need this arm for Phase 5
- [ ] Metrics from PLAN.md §7 are being logged. **From now on, not retroactively.**
