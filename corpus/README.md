# Corpus

`manifest.json` is the frozen, hand-curated list of `RepoSpec` entries (see
[../docs/interfaces.md](../docs/interfaces.md) §1 and
[../docs/phase-0-corpus.md](../docs/phase-0-corpus.md)). It is committed to git.

`candidates.jsonl`, `checkouts/`, and `logs/` are generated, gitignored, and safe to delete
— rerun the pipeline below to regenerate them.

## Pipeline

```bash
# 1. Discover candidates via GitHub commit-message and code search.
#    Requires GITHUB_TOKEN in your environment (see ../.env.example).
python -m pmigrate.corpus.discover

# 2. Mechanical validation (git/API only, no Docker needed): locate the real migration
#    commit, check it's isolated and non-trivial. Writes draft entries into manifest.json
#    and a drop-reason log to logs/drop_reasons.jsonl.
python -m pmigrate.corpus.validate

# 3. Docker-dependent validation: build each repo at pre_sha, run its suite twice for a
#    determinism check, gate on baseline pass rate, and sanity-check post_sha is green
#    under pydantic v2. Requires Docker Desktop installed and running.
python -m pmigrate.corpus.capture_baselines
```

Or via the CLI: `pmigrate corpus discover`, `pmigrate corpus validate`,
`pmigrate corpus capture-baselines`.

## After the pipeline runs

**Hand-curate before freezing** (docs/phase-0-corpus.md step 3): read every survivor,
reject trivial or toy migrations, and assign the `dev`/`test` split — stratified by repo
size and which pydantic features it uses, so the two splits aren't accidentally different
in difficulty. Then commit `manifest.json`.

Once frozen, treat the manifest as a versioned artefact: record its content hash in every
eval run's manifest (invariant I6, PLAN.md §2), and don't edit it casually — changing the
corpus invalidates prior eval numbers.
