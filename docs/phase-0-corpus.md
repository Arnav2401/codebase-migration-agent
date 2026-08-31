# Phase 0 — Corpus and infrastructure

**Est. 1.5 weeks. This is the phase everyone underestimates by 3×. Start it first, and keep
discovery running in the background through Phase 1–2.**

## Why this exists

Pydantic v1→v2 was chosen over every other migration for exactly one reason: **hundreds of
repos have already done it publicly**, so for each repo you get the human's answer for free.
Check out the parent of the migration commit, run the agent, compare against what the human
actually did. That gives you two metrics instead of one and turns a demo into an evaluation.

None of that works if the corpus is bad. A repo whose tests were already red before the
migration teaches you nothing and silently corrupts your pass rate.

## Deliverable

`corpus/manifest.json` — 30–40 validated `RepoSpec` entries (see interfaces.md §1), each with:
- pre/post commit SHAs
- a **green baseline** captured at `pre_sha` on pydantic v1
- a reproducible Docker build recipe
- a `dev`/`test` split assignment (roughly 12 dev / 22+ test)

## The funnel

Expect ~500 candidates → ~40 usable. Budget for that ratio.

### Step 1 — discovery (`corpus/scripts/discover.py`)

Search GitHub for repos that performed the migration. Cast a wide net, several queries:

- Commit/PR search: `pydantic v2`, `migrate to pydantic 2`, `bump pydantic`, `pydantic>=2`
- Code search for the diff signature: commits that change `pydantic~=1` / `pydantic<2` in
  `requirements*.txt`, `pyproject.toml`, `setup.py` to a v2 constraint
- Commits that introduce `model_validator`, `field_validator`, `ConfigDict`, `model_dump`,
  or `from pydantic_settings import`

Prefilter on repo metadata: has `tests/` or `test_*.py`, ≥20 stars (a proxy for a real
suite), <50 MB, Python-primary, permissive licence, last commit not ancient.

Output: `corpus/candidates.jsonl`. Do not hand-curate yet.

### Step 2 — mechanical validation (`corpus/scripts/validate.py`)

For each candidate, in order, dropping on first failure and **recording the drop reason**:

1. The migration commit is a *migration*, not a drive-by — touches ≥3 files, or ≥1 model file
   plus a dependency file. Reject commits that only bump a version pin (nothing to learn).
2. The migration is *isolated* — the commit doesn't also add a feature. Heuristic: reject if
   it touches >40 files or adds >30% net new lines. Imperfect; a human reviews the survivors.
3. Buildable at `pre_sha`: a Docker image builds and deps install. Cap debugging at **30
   minutes per repo**, then drop it.
4. Test suite runs at `pre_sha` in <10 min under pydantic v1.
5. **Baseline is meaningfully green**: ≥80% of collected tests pass, and ≥15 tests pass.
   Record the exact passing set — that set, not the whole suite, is the denominator (I4).
6. Sanity check the other end: at `post_sha` with pydantic v2, the human's version is green.
   If the human's own migration doesn't pass, the repo is not ground truth.

The drop-reason table is worth keeping. "127 of 500 candidates couldn't be built at all"
is a real finding and makes a good README paragraph.

### Step 3 — human curation

You read the survivors. Reject anything where the "migration" is trivial or the repo is a
toy. Assign `dev`/`test` split — **stratify** by repo size and by which pydantic features it
uses, so the splits aren't accidentally different in difficulty.

### Step 4 — freeze

Commit `manifest.json`. Record its sha256 in every eval run manifest (I6). Changing the
corpus after you have numbers means re-running everything; treat it as a versioned artefact.

## Fallback if the funnel yields <15 repos

**High-likelihood risk.** Two escape hatches, in order of preference:

1. **Relax the green-baseline threshold to a green *subset*.** Many repos have a handful of
   perpetually broken tests. Scoring only the baseline-passing subset (I4) already handles
   this correctly — you can drop the ≥80% gate to ≥50% without dishonesty.
2. **Synthesize.** Take modern pydantic-v2 repos and apply *reverse* codemods to produce v1
   code, then use the real repo as ground truth. This is legitimate but weaker (the v1 code
   is synthetic and unnaturally uniform). If you use it, **say so prominently in the README
   and report synthetic and real corpora as separate numbers.** Never blend them into one
   headline figure.

## Also in this phase

- Install Docker Desktop (not currently on this machine).
- `docker-compose.yml` with Neo4j 5 community + a volume.
- `pyproject.toml`, `Makefile`, ruff/mypy config, pre-commit.
- `src/pmigrate/types.py` with the shared dataclasses from interfaces.md.

## Acceptance criteria

- [ ] `make corpus` validates the manifest and reproduces every baseline from scratch
- [ ] ≥30 repos (or a documented fallback in use), each with a recorded baseline pass set
- [ ] Drop-reason histogram written to `docs/results/corpus.md`
- [ ] Two runs of baseline capture produce identical pass sets (determinism check)
- [ ] dev/test split assigned and stratified

## Pitfalls

- **Flaky tests poison baselines.** Capture each baseline twice; any test that disagrees
  between runs goes in a `flaky` set and is excluded from scoring.
- **Network-dependent tests.** Many suites hit the internet. The sandbox has no network at
  run time, so those tests fail in your baseline and get excluded automatically — which is
  correct, but check you aren't excluding 90% of a repo's suite.
- **`pip install` resolving differently over time.** Pin a resolution: generate and commit a
  lockfile per repo at validation time, or pin the index date.
