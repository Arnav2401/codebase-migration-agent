# Phase 2 — Sandbox and test runner

**Est. 1 week.**

## Why this exists

Two reasons, and you should give both:

1. **It is the only source of truth in the system.** Every claim the agent makes is
   validated here. If the runner is flaky or non-deterministic, every number downstream
   is noise.
2. **It is a live security boundary.** You are executing model-generated code against
   arbitrary GitHub repositories on your machine.

## Deliverable

`Sandbox` (interfaces.md §3): build a cached image per `(repo, sha, deps-hash, pydantic
version)`, then run the suite with no network and hard resource caps, returning
**structured** results — never a raw log string.

## Design

### Two-stage isolation

Installing dependencies needs the network. Running tests does not.

- **Build stage** — network on, runs once per repo, heavily cached. Produces an image with
  deps installed and the repo at `pre_sha`.
- **Run stage** — `--network none`, repo mounted **read-only**, agent edits applied as a
  writable overlay (`overlayfs` or a copy-on-write bind of a scratch dir), `--tmpfs /tmp`,
  `--memory`, `--cpus`, `--pids-limit`, `--cap-drop ALL`, non-root user, wall-clock timeout.

The read-only mount means a runaway edit or a malicious repo can never corrupt the corpus
checkout — you can always reset to a known state for free.

### Image caching

Cache key: `repo_id + sha + hash(dependency files) + pydantic_version`. This is the
difference between a 40-repo eval taking 45 minutes and taking 6 hours. Build it in on day
one, not as an optimisation later.

### Structured results

Run pytest with a JSON reporter (`pytest-json-report`, or parse `--junit-xml`) plus
`-p no:randomly` for determinism. Return `TestRun` with per-test node ids, statuses,
trimmed tracebacks, and — critically — **`collection_errors` as a separate field**.

A pydantic v2 migration usually fails at *import time*, so the suite collects zero tests and
pytest exits non-zero with one traceback. If you only look at test outcomes you see "0
failures" and conclude success. Handle this explicitly; it is the single most common failure
mode of the whole project.

### Truncation

Tracebacks and stdout can be enormous. Trim at capture time with a documented policy (first
N lines + last N lines of each traceback, cap total payload), set `truncated=True`, and keep
the full log on disk next to the trace. Never send an untrimmed log to a model.

### Selective re-runs

`run_tests(selection=[node_ids])` so triage can re-run only the failures after a targeted
fix. This is a large cost and latency saving in Phase 4. Always do a **full** run before
declaring success.

## Acceptance criteria

- [ ] Every corpus repo builds and runs its suite in the sandbox
- [ ] Repeated runs on unchanged input give byte-identical pass/fail sets
- [ ] Network is provably off at run time (a test that asserts a socket connection fails)
- [ ] A deliberately hostile fixture (infinite loop, fork bomb, 10GB allocation, file write
      outside the overlay) is contained and reported as a clean failure, not a hang
- [ ] Image cache hit turns a repeat run into <10s of overhead
- [ ] Collection errors are surfaced distinctly from test failures

## Pitfalls

- Repos with `conftest.py` that needs network/db at collection: mark them in the manifest
  with `setup_overrides` or drop them.
- Docker on macOS is a VM — expect slower IO than you think, and set memory limits that
  actually fit inside Docker Desktop's VM allocation.
- Don't `docker exec` into a long-lived container to save startup time until the numbers
  exist. Fresh container per run is worth the seconds for determinism.
