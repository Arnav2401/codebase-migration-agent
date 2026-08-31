# Working agreement

This repo is a learning project as much as a shipping one. The value is Arnav being able
to defend every architectural decision in a 15-minute interview. Code he didn't reason
through is worth less than code he did.

## How to work here

1. **Interfaces before implementations.** When starting a component, propose the module
   structure, type signatures, and data contracts first. Wait for agreement. Then implement.
2. **Explain trade-offs, don't just produce.** When you pick an approach, name the
   alternative you rejected and why in one sentence. Add it to `docs/decisions.md` if it's
   load-bearing.
3. **Don't write whole components unprompted.** Scaffold, stub, review, unblock. If Arnav
   asks "implement X", implement X — but if he asks "how should X work", answer, don't build.
4. **Review diffs adversarially.** When asked to review, look for: silent failure paths,
   invariant violations (see PLAN.md §2), untested branches, and places where the code
   would produce a *number* that isn't honest.
5. **Never let a metric be computed in more than one place.** All scoring lives in
   `src/pmigrate/eval/metrics.py`.

## Invariants — check these on every change (PLAN.md §2)

- I1 agent never edits test files · I2 never skips/deletes tests · I3 never pins pydantic <2
- I4 only baseline-passing tests count · I5 dev/test split respected · I6 runs reproducible
- I7 PRs only to Arnav's own forks

If a change could violate one, say so before writing it.

## Conventions

- Python 3.11, `src/` layout, `pyproject.toml` with hatchling.
- `ruff` + `ruff format`, `mypy --strict` on `src/pmigrate/` (not on tests).
- Types everywhere. Dataclasses (frozen where possible) or Pydantic v2 models for
  contracts — note the irony and enjoy it.
- No bare `except:`. No `print()` outside `cli/` — use `structlog`.
- Every module that touches money or time logs to the trace (`src/pmigrate/trace/`).
- Tests mirror `src/` paths. `pytest`, no network in unit tests.
- Prompts live in `src/pmigrate/agent/prompts/*.md`, are versioned, and are hashed into
  the run manifest. Never inline a prompt in Python.

## Build order — do not skip ahead

Phases are in `docs/phase-*.md`. Each has explicit acceptance criteria. Phase N+1 does not
start until Phase N's criteria are demonstrably met. Phases 6+ are locked until
`docs/results/main.md` contains real measured numbers.

## Commands

```bash
make setup      # venv, deps, pre-commit
make neo4j      # docker compose up neo4j
make lint       # ruff + mypy
make test       # pytest on OUR code
make corpus     # validate corpus manifest, rebuild baselines
make eval CONFIG=configs/main.yaml SPLIT=dev
```
