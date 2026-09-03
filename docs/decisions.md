# Decision log

Every entry: the decision, the alternative rejected, the reason, and **the sentence you say
in an interview**. If you can't fill in the last field, the decision isn't made yet.

Add to this file whenever you make a load-bearing choice. It is the source material for the
"walk me through a hard decision" part of an interview, which is 15 of your 20 minutes.

---

## D1 — Pydantic v1→v2 as the migration target

**Alternatives:** SQLAlchemy 1.x→2.0 · Python 2→3 · unittest→pytest · a generic
"any migration" agent.

**Why:** ground truth is free. Hundreds of repos have done this migration publicly, so for
every task you have the human's answer sitting in git. That converts a demo into an
evaluation with two metrics (test pass rate *and* similarity to the human diff) instead of
one. Secondary: breaking changes are exhaustively documented, blast radius per repo is
small enough to be tractable, and demand is still live.

**Interview:** "I picked it because the migration has already been done publicly hundreds of
times, which means every task in my corpus comes with the human's answer attached. That's
what let me build a real evaluation instead of a demo."

---

## D2 — Neo4j for the code graph

**Alternatives:** networkx in memory · SQLite with recursive CTEs · a vector store only.

**Why:** the queries are variable-length graph traversals ("everything that transitively
imports this, up to depth 3, along these edge kinds"), which Cypher expresses directly and
recursive SQL expresses painfully. It's also a persistent store, so graph construction is
decoupled from the agent process — you ingest once and every eval arm queries the same graph.

**Honest caveat you should volunteer:** for a single repo, networkx would be enough, and
the code is written against a `CodeGraph` protocol precisely so the backend is swappable.
Neo4j earns its place at corpus scale and because the query language is the right level of
abstraction, not because graphs-are-cool.

**Interview:** "Cypher expresses transitive dependency traversal directly, and I needed a
persistent store so ingest was decoupled from the agent. I also wrote it behind a protocol —
for one repo networkx would do, and I want to be honest that Neo4j is earning its keep at
corpus scale rather than being load-bearing for correctness."

---

## D3 — Graph retrieval over embedding retrieval

**Alternative:** embed code chunks, retrieve by cosine similarity (the default RAG move).

**Why:** what matters for a migration is which symbols *call* which, not which files *sound*
similar. And the graph gives an **ordering** — you must migrate a module before its
dependents, which is a topological sort. Similarity scores cannot express that.

**Backed by measurement, not assertion:** this is ablation arm `embedding` in Phase 5, run
with everything else identical. If the gap is small, the honest thing is to report the small
gap.

**Interview:** "Embeddings retrieve what sounds similar; migration needs what's connected,
and it needs an order. I ran both arms with everything else held constant and measured the
difference rather than assuming it."

---

## D4 — Hybrid edit strategy: deterministic codemods before the LLM

**Alternative:** LLM-only agent (the obvious build) · codemod-only (the `bump-pydantic`
approach).

**Why:** ~80% of a Pydantic v1→v2 diff is mechanical renaming. Spending frontier-model
tokens on `.dict()` → `.model_dump()` is expensive, slow, and adds sampling variance to a
transformation that has exactly one right answer. Codemods handle those deterministically
and for free; the model's budget goes to the semantic 20% — implicit-Optional defaults,
coercion strictness, custom validator protocols — where it's actually needed.

It also gives you a free third ablation (T1-only vs. hybrid vs. LLM-only), which tells you
precisely where the model earns its cost.

**Interview:** "Most of this migration is deterministic, so I wrote codemods for it and spent
the model on the parts that need judgment. Then I measured all three configurations — the
codemods alone get you a long way, and knowing exactly how far is the interesting part."

---

## D5 — Rule-first triage, LLM only as fallback

**Alternative:** dump the pytest log into the context and let the model figure it out.

**Why:** a 4000-line log buries the signal and costs a fortune. Classification by regex and
traceback parsing is deterministic, testable, nearly free, and — the key part — lets each
failure class carry its own **allowed edit surface**. A third-party version conflict gets a
strategy that can only touch dependency files, so the model can't "fix" it by rewriting
models.

**Interview:** "A dependency conflict and a coercion-semantics change are completely
different problems that both look like a red test. Classifying them lets me constrain what
the model is even allowed to edit for each one."

---

## D6 — Only baseline-passing tests count (invariant I4)

**Alternative:** score against the full suite.

**Why:** real repos have tests that were already failing before the migration. Counting
those makes your pass rate look worse than reality — or, if you're careless about which
direction, lets a repo look green because its suite never ran. Capturing the exact set of
tests that passed pre-migration and scoring only against that set is the only honest
denominator.

**Interview:** "I recorded which tests passed *before* the migration and scored only against
that set. Otherwise I'd be crediting or blaming the agent for failures that had nothing to
do with it."

---

## D7 — dev/test corpus split, test split run at most three times (invariant I5)

**Alternative:** iterate on all 34 repos.

**Why:** prompt engineering against your whole corpus is overfitting with extra steps. You
will absolutely convince yourself a prompt tweak is a real improvement when it's noise on
twelve repos. A held-out split you barely touch is the only way the final number means
anything.

**Interview:** "I split the corpus and only ran the held-out half at the very end. Every
prompt change I made was scored on the dev half — otherwise the final number is just
memorised."

---

## D8 — No multi-agent orchestration

**Alternative:** planner / editor / verifier as separate agents.

**Why:** the split would be cosmetic. The loop is already a state machine with distinct
nodes; wrapping each node in its own agent adds coordination overhead, more failure modes,
and more cost for no measured gain. If the problem demands the split later, the state
machine already has the seams. "Multi-agent" as a feature claim is increasingly a negative
signal.

**Interview:** "I have a planner, an editor, and a verifier — they're nodes in a state
machine, not separate agents. The split exists where it earns something; I didn't add
coordination overhead to be able to use the word."

---

## D9 — Fork before opening PRs (invariant I7)

**Alternative:** open PRs directly against the upstream repos.

**Why:** unsolicited AI-generated PRs against real maintained projects waste maintainers'
time and are a bad look on a portfolio. The workflow is identical against a fork, so there's
no demonstration value lost.

**Interview:** "The PR workflow runs against my own forks. Opening machine-generated PRs on
projects I don't maintain would be discourteous, and it doesn't prove anything the fork
doesn't."

---

## D10 — Tool-layer enforcement over prompt-based rules

**Alternative:** instruct the model not to edit tests, not to skip, not to downgrade pydantic.

**Why:** a prompt is a suggestion; `apply_patch` is a chokepoint. Every write goes through
one function, and that function enforces I1–I3 mechanically. This is also the real
prompt-injection defence: no instruction planted in a repo's docstrings can grant a
capability the tool layer doesn't allow. Detection is defence in depth, not the mechanism.

**Interview:** "All the invariants are enforced in the single function that applies patches,
not in the prompt. That's also why prompt injection through repo comments can't do much —
it can influence what the model *wants* to do, but not what the tool layer permits."

---

## D11 — Built the in-memory CodeGraph backend first, and it's what's actually tested

**Alternatives:** wait for Neo4j to be available and build only that · mock the Neo4j
driver in tests.

**Why:** D2 already pre-approved this swap ("the in-memory networkx backend is a 1-day
swap... don't let it block Phase 3"), and Neo4j wasn't installed while Phase 1 was being
built. Rather than writing Cypher I couldn't run and calling it done, the CodeGraph
protocol was implemented twice against the identical shared graph-construction function
(`build.py`): once as plain Python dicts (`memory_store.py`, exercised by the full test
suite — ingest, dependents, dependencies, topo_modules, neighbourhood, all passing against
a hand-built fixture repo), once as real Cypher (`store.py`, matching the documented schema
but never run against a live database). Mocking the driver would have given false
confidence — a mocked `execute_query` proves the code calls the mock correctly, not that
the Cypher is right. An actually-working alternate backend proves the *contract* is right,
which is what Phase 3 needs from this layer regardless of which backend eventually runs.

**Also note, honestly:** neither backend populates CALLS or REFERENCES edges (one
first-party symbol calling/using another) — that needs scope-aware name resolution that
wasn't built. `dependents`/`dependencies` today answer via CONTAINS, IMPORTS, and INHERITS
only. See build.py's docstring for the full scope statement.

**Interview:** "I built the graph against a protocol and implemented it twice — once as a
tested in-memory backend, once as real but unverified Cypher — because Neo4j wasn't
available while I was building this, and a mocked database test would have proven the code
calls a mock correctly, not that the queries are right. The in-memory version is what
actually proves the interface works."

---

## D12 — `--continue-on-collection-errors` is non-negotiable, always passed

**Alternatives:** run pytest with default flags and treat an empty `tests` list as "the
suite passed" · only add the flag after seeing it bite once in eval data.

**Why:** verified locally, without needing Docker — a plain `pytest --json-report` run
against two files, one with a broken import and one with three perfectly good tests, stops
the *entire session* at the first collection error. The report comes back with
`tests: []`. Every one of the three good tests simply never ran; nothing distinguishes that
from "zero tests, zero failures, migration successful." Since a pydantic v2 migration's
most common failure mode is exactly an import-time break (docs/phase-2-sandbox.md says so
explicitly), a sandbox that doesn't pass this flag would report the single most common
failure case as a clean pass. This is not a hypothetical edge case caught by defensive
programming — it's the default, undecorated behavior of the tool everything else is built
on, and it took one local run with no Docker involved to see it.

**Interview:** "Before writing the JSON-report parser, I ran pytest locally against a
broken-import fixture to see exactly what the output looks like. Without one specific flag,
pytest aborts the whole session on the first collection error and the report shows zero
tests — which is indistinguishable from success unless you know to look for it. That's not
a corner case for this project; it's the single most common way a v1→v2 migration actually
fails. I'd rather find that by testing the tool I'm building on than by watching my agent
report false positives for a week."

---

## D13 — Every sandbox container gets an explicit `--name`, force-killed on timeout

**Alternatives:** rely on `subprocess.run(..., timeout=...)` to kill the runaway process ·
rely on `--rm` to clean up eventually.

**Why:** found by actually running the hostile-fixture test (an infinite `while True: pass`)
against a live Docker daemon, not by reasoning about it in advance. `subprocess.run` on
timeout kills the **client process** it started — but `docker run` (foreground, no `-d`) is
just a thin client attached to a container the *daemon* manages independently. Killing the
client does nothing to the container. Confirmed directly: `docker ps` a full minute after
the Python-level timeout fired showed the container still `Up`, pinned at 99.9% CPU,
completely un-contained — exactly the failure mode docs/phase-2-sandbox.md's acceptance
criteria explicitly calls out ("contained... not a hang") and exactly what the code, before
this fix, silently failed to guarantee despite *looking* like it handled timeouts correctly
(it caught `TimeoutExpired` and returned a clean `TestRun`; the container just kept running
anyway).

Fix: every container gets a unique generated name (`policy.build_run_args` requires
`container_name`); on `TimeoutExpired`, `runner.py` runs `docker kill <name>` explicitly.
Combined with `--rm`, killing the container is what triggers its removal — `--rm` alone,
without something actually stopping the container, never fires.

**Also found in the same verification pass, smaller but real:** the image cache key
(`compute_deps_hash`) hashed per-repo config but not the Dockerfile/entrypoint template
content itself — so fixing the bug above and rebuilding would have silently kept serving
the OLD, broken cached image under the same tag. Fixed by folding the template strings into
the hash too.

**What this proves, worth saying explicitly:** the unit tests for `runner.py` (mocking
`subprocess.run`) all passed *before* this bug was found — mocks proved the orchestration
logic did what I told it to, which was itself incomplete. Only running against a real
daemon surfaced that "catch the timeout and return cleanly" and "actually contain the
process" are two different guarantees.

**Interview:** "My timeout handling looked correct and passed every unit test, because the
tests mocked `subprocess.run` and only checked that my code reacted correctly to a timeout
— they couldn't check whether the container back on the real daemon was actually stopped.
Running the hostile fixture against live Docker showed a container still running a full
minute later at 99% CPU. The fix was naming every container explicitly and force-killing it
by name, and I only trust that fix because I reran the same fixture and confirmed `docker
ps` comes back empty afterward."

---

## D14 — `cp -r`, not `cp -a`, in the sandbox entrypoint

**Alternatives:** run the entrypoint as root, then `su`/`gosu` down to the non-root user
before invoking pytest · skip the copy step and run pytest directly against `/repo-base`.

**Why:** the very first live run against Docker failed immediately — every container
exited before pytest ran, with `cp: preserving times for '/repo/.': Operation not
permitted`. `cp -a` (archive mode) tries to preserve ownership and timestamps as part of
copying; the sandbox intentionally runs as a non-root, unprivileged user (`nobody`,
policy.py's `NOBODY_UID_GID`) with no permission to set those attributes on a tmpfs it
doesn't own. Because the entrypoint script has `set -e`, that one non-fatal-looking warning
line was actually a non-zero exit that aborted the container before `exec "$@"` ever ran —
so from the *outside*, this looked exactly like "no json report produced," indistinguishable
from an OOM kill or a genuine crash, until the actual docker command was run by hand outside
`subprocess.run`'s captured output.

Running as root and dropping privileges afterward would work but adds a second moving part
(a privilege-drop tool, more Dockerfile surface) for a copy that doesn't need ownership or
timestamps preserved at all — pytest doesn't care when a file's mtime is, and nothing reads
it. `cp -r` copies contents without touching either, which is exactly what's needed here.

**Interview:** "The entrypoint failed on the very first real run, and the error was subtle —
`cp -a`'s failure looked like a warning, not a hard stop, until I noticed the script has
`set -e`. The actual fix was one flag, but finding it meant running the container manually
outside my own code, because `subprocess.run`'s captured stderr was getting swallowed by my
own error handling before I looked at it directly."

---

## D15 — apply_patch's invariant checks, verified against adversarial-shaped test input

**Alternatives:** trust the regexes as written · test only the happy path (a clean rewrite
applies correctly).

**Why:** writing tests specifically shaped to break I3 (the pydantic-pin check) — not just
tests that confirm it works — found that the first regex only matched an EXACT `1` as the
upper or exact bound (`pydantic<1`, `pydantic==1.x`). It never matched `pydantic<2`, which
is the actual common way a dependency file permanently excludes v2 (a floor doesn't matter;
the ceiling does). A model trying to sneak a v1 pin back in would almost certainly write
`<2`, not `<1` — the exact case the first version missed. Fixed by checking for the ceiling
(`<2`) directly rather than pattern-matching for the literal digit `1`.

Same session, a second real bug in the revert path: `apply_patch`'s post-apply syntax check
tried to undo a bad patch via `git checkout -- <files>`, which does nothing (no error,
silently no-op or fails) when the working directory isn't a git repository — exactly the
shape of Phase 2's real overlay staging directory, which is a plain directory by design
(see docs/phase-2-sandbox.md). The test that caught it used a plain `tmp_path`, not a git
repo, specifically because that's what the real caller actually looks like. Fixed by
snapshotting original file content in memory before applying, and restoring from that
snapshot on failure — independent of git entirely.

**Interview:** "The invariant checks are the part of this project I trust least by default,
because they're the actual safety boundary — so I wrote tests aimed at breaking them, not
just tests confirming the obvious case. Both real bugs I found came from asking 'what would
this miss' rather than 'does this work': the pydantic-pin regex only caught an exact `1`
where the realistic attack is a `<2` ceiling, and the revert logic assumed a git repo that
the actual calling context — a plain overlay directory — never has."

---

## D16 — `--format=%H`, not `--oneline`, when extracting a commit SHA from git log

**Why (brief — a data-quality bug, not a design decision):** `validate.py`'s git-log
heuristic for locating an unlabeled migration commit used `git log --oneline`, which
abbreviates hashes to 7 characters by default. That's fine for a human skimming output, not
for a value stored as `post_sha` and later passed to `git checkout`/the GitHub API — found
only by inspecting a real manifest entry (`madkote/fastapi-plugins`'s `post_sha` was
`bba8e76`, while every commit-message-sourced entry had a full 40-char SHA) and noticing the
inconsistency. Short SHAs happen to still work with both git and the GitHub API, so this
wasn't causing failures yet — it would have eventually, silently, if a short SHA ever
collided with another commit in a larger repo. Fixed by using `--format=%H`.

---

## D17 — The first real end-to-end run, and what it actually found

**Context:** the first genuine end-to-end run of the whole pipeline (graph → relevance →
work_list → T1 codemods → real Docker sandbox) against a real corpus repo,
`madkote/fastapi-plugins` at its pre-migration commit. Three real, distinct problems
surfaced, none of them visible from unit tests against synthetic fixtures — this is the
argument for corpus-based evaluation over fixture-only testing, made concrete.

**1. A fundamentally unsatisfiable pip resolution, disguised as a slow build.** The
sandbox pinned `pydantic>=2` BEFORE running the repo's own `pip install -e .[test]` — but
the repo's `setup.py`, correctly for its pre-migration state, declares `pydantic<2.0.0`.
Pip's resolver doesn't detect "these two constraints can never both hold"; it backtracks
through dozens of `fastapi` versions searching for a combination that satisfies both,
forever. This silently ate the full 30-minute build timeout on the very first attempt —
indistinguishable from "just slow" until watched directly (`docker build` without captured
output). Fixed by installing the repo's own dependencies FIRST, then force-reinstalling
the target pydantic version afterward as a separate, non-resolving step — full write-up in
`image.py`'s module docstring.

**2. The `basesettings_import` codemod only handled one of two real syntactic forms.**
`from pydantic import BaseSettings` was covered; `import pydantic` + qualified
`pydantic.BaseSettings` access (exactly what `fastapi_plugins/plugin.py` does) was not. The
rule reported success and changed nothing that mattered — the exact
`PydanticImportError: BaseSettings has been moved` persisted after the "fix." Full
write-up and fix in `basesettings_import.py`'s module docstring; regression test uses the
literal real source shape, not a paraphrase.

**3. A rewritten import needs the package it imports to actually be installed.** After
fixing (2), the error changed to `ModuleNotFoundError: No module named 'pydantic_settings'`
— syntactically correct code, missing dependency. `pydantic-settings` is now installed
unconditionally alongside pydantic v2 in every sandbox image, since the codemod that
produces `import pydantic_settings` deliberately never touches dependency files itself
(that's a real external action, out of scope for a rule operating on one file — see the
same docstring). Separately, `fastapi-plugins`' own `setup.py` doesn't declare `httpx` as
an installable test extra (`pip install -e .[test]` warns "does not provide the extra
'test'"), so its test suite can't collect in a clean sandbox at all — fixed via this repo's
`setup_overrides` manifest field, exactly the escape hatch it exists for, not a code change.

**Interview:** "The first real end-to-end run — not a fixture, an actual repo — found three
things unit tests never would have: a pip resolution that could never finish, a codemod
that silently did nothing for a syntactic pattern I hadn't tested, and a fix that was
correct code but missing its own dependency. None of these were visible until I watched a
real migration attempt fail for a real reason. That's the whole argument for the corpus
being made of real repos instead of synthetic ones."

---

## D18 — T1 processes the whole work list eagerly, not one unit per test cycle

**Alternatives:** keep the original one-unit-at-a-time design (edit unit → test → route
→ next unit only if green) uniformly for all tiers.

**Why:** a second real end-to-end run on the SAME repo (after fixing D17's three bugs)
surfaced a structural problem, not a codemod problem. `plugin.py` (unit 1 of 9) was fixed
correctly, but `control.py` (unit 2) — which independently needed the exact same
`pydantic.BaseSettings` rewrite — was never touched, because `route()` only advances to the
next unit after a fully green test run, and `plugin.py`'s fix alone wasn't enough to turn
the suite green. The loop gave up after one unit, leaving eight untouched, seven of which
needed nothing but the SAME already-correct, already-tested codemod fix.

One-unit-at-a-time gated on green is the right shape for T2/repair — you want tight
feedback per expensive LLM call. It actively works against T1, which is cheap, deterministic,
and doesn't need a test result to decide whether `.dict()` should become `.model_dump()`.
Fixed by having `edit_t1` process the ENTIRE remaining work list in one pass before the
first test run — matching docs/phase-3-loop.md's own framing more literally than the
original graph wiring did: "T1 codemods run first, unconditionally, before any LLM
involvement" means for the whole repo, not unit-by-unit gated on results.

**Interview:** "The second real run found an architecture bug, not a codemod bug — my loop
only moved to the next file after the current one's tests passed, which meant one file T1
couldn't fully fix blocked seven other files from getting fixes they definitely needed and
that had already been proven correct on a different file. The fix was applying every
mechanical rewrite across the whole repo up front, then testing once — which is also just a
more literal reading of my own design doc, which already said T1 runs 'unconditionally.'"

---

## D19 — T1 runs over every first-party file in the repo, not just `work_list`

**Alternatives:** extend `relevance.py`'s signal detection to also flag a file when
`pydantic.BaseSettings`/`BaseModel` appears in a bare type annotation (not just a class base
or a `.dict()`-shaped call), so `compute_work_list()` would have included the file.

**Why:** a THIRD real end-to-end run (after D18's fix) still left one file broken:
`fastapi_plugins/settings.py` — `def register(self, name: str, config:
pydantic.BaseSettings) -> None:` — still raised `PydanticImportError`. `ConfigManager`
doesn't inherit from `BaseSettings`; it only references it as a parameter type annotation.
`relevance.py`'s `class_signals()` was built to answer a planning question — "which classes
need symbol-level T2 attention, and how hard are they" — inheritance, nested `Config`
classes, and `.dict()`/`.json()`-shaped calls are real signals for THAT question. "a type
annotation somewhere in the file mentions `pydantic.BaseSettings`" isn't a symbol worth
planning around, so it was never a signal, so the file was never in `work_list`, so T1 never
even looked at it — the D18 fix processes the whole work list eagerly, but a file absent
from the list entirely is invisible to "the whole list" too.

Rejected the alternative (widen `class_signals()` to detect the annotation case) because it
treats a T1 scoping gap as a relevance-detection gap. `relevance.py`'s job is symbol-level
targeting for the expensive tiers; T1's codemods are cheap, deterministic, and already
test-gated by `run_tests` — there's no cost reason to scope them to relevance.py's narrower
planning set, and every new AST shape that can reference `pydantic.BaseSettings` (type
annotations, default values, `isinstance` checks, `TYPE_CHECKING` blocks, ...) would be
another one-off detector to maintain in a module that has no other reason to enumerate them.
Fixed by decoupling the two concerns: `edit_t1` now runs `ALL_RULES` over every first-party
`.py` file under `source_root` (via `graph/repo_files.read_py_files`, the same
first-party-file enumeration `resolve_repo()` already uses for ingestion), while
`work_list` still drives ordering and the `unit_module` label attached to each `Edit` for
provenance. Files outside `work_list` get a display-only module name derived directly from
their path.

**Interview:** "Two different real bugs looked similar but weren't: D18 was about WHEN T1
touches files already on its list; D19 was about a file that was never on the list at all,
because the list is built by a detector designed to find classes worth planning around, not
'anything that mentions this symbol.' Rather than teach the planner to recognize every shape
a stray reference could take, I decoupled scope from planning — T1 is cheap and test-gated,
so it just runs everywhere; the work list still does its real job of ordering and
difficulty-scoring for the tiers that actually cost money."

---

## D20 — T1-only's real ceiling on `madkote/fastapi-plugins`: 22/23, and why the gap is real

**Alternatives:** keep iterating T1 codemods/relevance detection until this repo goes fully
green.

**Why:** after D19's fix, the SAME real end-to-end run went from 0 collectible tests to
22/23 passing — every `PydanticImportError`/`NameError` collection failure is gone, across
all 9 real modules the human migration PR itself touched
(`corpus/manifest.json`'s `human_diff_stats.changed_paths` independently lists
`plugin.py`, `control.py`, `logger.py`, `_redis.py`, `scheduler.py`, `memcached.py`,
`settings.py` — the exact same set T1 now reaches). The remaining failure
(`tests/test_scheduler.py::test_endpoints`) and two of the four remaining collection errors
are NOT codemod gaps:

- `ModuleNotFoundError: No module named 'aiomcache'` (memcached/test_memcached,
  test_control): the manifest's `install_cmd` is `pip install -e .[test]`, and that extra
  doesn't pull in `aiomcache`. This is corpus-curation data (which extras to install),
  not agent behavior — and the human's own migration PR didn't touch `setup.py`'s extras
  either, so this gap almost certainly predates the migration entirely.
- `ValidationError: Input should be a valid string [type=string_type, input_value=None]`
  on `RedisSettings`/`LoggingSettings`/`AppSettings` fields declared as bare `str` with a
  `None` default: pydantic v1 coerced an unset env var against a `None` default leniently;
  pydantic-settings v2 is strict about the declared type not matching `None` unless the
  field is `Optional[str]`. This is a genuine semantic behavior change — exactly
  `FailureClass.VALIDATION_BEHAVIOUR` in docs/interfaces.md §6's own taxonomy — not a
  mechanical rename T1 rules could or should attempt (turning `str` into `str | None`
  changes the field's actual contract, which is a judgment call, not a rewrite).

Not chasing this further: fixing it needs T2 (semantic, LLM-assisted repair), which is
already correctly gated behind `ModelClient` and blocked on there being no API key in this
environment (agent/graph.py, agent/model_client.py docstrings) — the same documented
boundary as before D16–D19, not a new one. Continuing to patch T1 rules to guess at type
widening would blur exactly the T1/T2 line the project's tiering is built around.

**Interview:** "The T1-only arm's whole thesis is that mechanical rewrites get you most of
the way and semantic judgment calls need a model — this run is the clean confirmation. It
went from completely uncollectable to 22 of 23 tests passing with zero LLM calls, and the
one real remaining failure isn't a bug in my rewrites, it's pydantic v2 actually being
stricter about type/default consistency than v1 was — which is precisely the
'validation_behaviour' category I designed the triage taxonomy around before ever running
this. I could patch around it by having a codemod guess `Optional` in these cases, but that
changes program semantics based on a heuristic, exactly the class of edit this project
reserves for a model with judgment, not a rule with a pattern match."

---

## D21 — `plugboard-dev/plugboard`'s manifest was wrong on two unverified TODOs

**Alternatives:** switch this repo's build to `uv sync` (it ships a `uv.lock` and a
`[tool.uv.workspace]`), instead of patching around `pip install -e .[test]`.

**Why:** trying the second dev-split repo to see whether T1-only could reach a fully green
run on ANY corpus repo (docs/phase-3-loop.md's still-open acceptance criterion) hit a Docker
build failure, not a codemod problem. Two real, distinct manifest defects, both already
flagged as unverified by `corpus/validate.py`'s own `# TODO(human): confirm per-repo` /
`# TODO(human): verify per repo` comments on `python_version` and `install_cmd` — i.e. this
repo was marked dev-split before that verification step was actually done:

1. `python_version` was hardcoded to `"3.11"` for every corpus repo at manifest-build time.
   `plugboard`'s `pyproject.toml` at `pre_sha` declares `requires-python = ">=3.12,<4.0"` —
   confirmed by cloning and checking directly — so pip refused every candidate version of
   the repo's own package outright.
2. `plugboard` is a two-package `uv` workspace (`plugboard` + `plugboard-schemas`, a local
   sibling directory declared via `[tool.uv.sources] plugboard-schemas = {workspace =
   true}`). `pip install -e .[test]` has no idea what a uv workspace source is — it just
   tries to fetch `plugboard-schemas` off PyPI and fails with "No matching distribution
   found." Confirmed by reproducing the exact `docker build` locally with a hand-rendered
   Dockerfile and reading pip's actual stderr (`subprocess.run(..., capture_output=True)`
   in `image.py` swallows it into `CalledProcessError.stderr` on an uncaught exception,
   so the traceback alone didn't show the real cause — had to re-run the build directly).

Rejected switching to `uv sync` for now: it would fix this repo more natively, but adds a
second install pathway (`uv` vs `pip`) to the Dockerfile template for a problem with a
one-line fix under the mechanism that already exists (`setup_overrides`) — not worth the
generality when N=1 repo needs it so far. Fixed by correcting the manifest directly:
`python_version="3.12"`, and `setup_overrides=("RUN pip install -e
/repo-base/plugboard-schemas",)` so the workspace member is a real installed distribution
by the time `pip install -e .[test]` goes looking for it.

**Interview:** "The corpus curation script left two fields explicitly marked
'TODO: verify per repo' — hardcoded Python 3.11 and a bare `pip install -e .[test]` — and
this repo was the one where skipping that verification actually mattered: it needs 3.12 and
it's a uv workspace with a local sibling package pip can't resolve on its own. I found both
by reproducing the failing `docker build` directly instead of trusting the wrapped
`CalledProcessError`, which had already swallowed the real pip output. Fixed it with the
same `setup_overrides` mechanism I already had for fastapi-plugins' httpx dependency, rather
than introducing `uv` as a second install pathway for one repo."

---

## D22 — codemod rules run under a per-rule exception boundary, not bare trust

**Alternatives:** patch only the specific rule that crashed (`validator_to_field_validator`)
and leave `apply_rules` as a bare loop with no exception handling.

**Why:** the rerun against `plugboard-dev/plugboard` (after D21's manifest fix got the
Docker build working) hit an uncaught `AssertionError` inside
`validator_to_field_validator.py`: it assumed every decorator literally named `validator`
was pydantic's `@validator(...)`, always called with an argument. `plugboard-schemas`
defines its OWN, unrelated decorator — `from ._validator_registry import validator`, used
bare with no call — and the name-only match (no import-provenance check) collided with it.
Confirmed by cloning the repo at `pre_sha` and reading the actual source
(`plugboard-schemas/plugboard_schemas/_validation.py`).

Because `edit_t1` (D18) processes every file in the repo in one call, this single crash
aborted the ENTIRE run — the 30 other units' independent, already-correct fixes were
discarded along with it, LangGraph's `.invoke()` propagating the exception straight out.
Fixing only the one assertion (which I also did — a bare, uncalled `@validator` is never
valid pydantic v1, so it's now left untouched rather than assumed-and-crashed) treats this
as a one-off. It isn't: every T1 rule is a heuristic pattern-match on source SHAPE, not a
verified semantic check (protocol.py's own docstring already says this) — any of them can
hit a shape its author didn't anticipate on arbitrary third-party code, which is a genuine
system boundary (CLAUDE.md: "Only validate at system boundaries"), not internal state under
this project's control. Fixed generically: `codemod/engine.py`'s `apply_rules` now wraps
each rule's `.apply()` call, logs the failure (`codemod.rule_failed`, rule id + path +
error) via the same structlog convention as the rest of the codebase, and continues with
the tree as it was — exactly how a `git apply`-rejected patch is already handled one level
up in `edit_t1`, generalized to the rule layer itself.

**Interview:** "The bug that crashed the whole run wasn't really 'my regex-shaped rule had a
gap' — it was 'I trusted user-controlled, arbitrary third-party source to never violate an
assumption baked into an `assert`.' The one-line fix (don't assume `@validator` is always
called) fixes the symptom. The real fix is architectural: T1 runs on code I don't control
and rules that are explicitly heuristic, so `apply_rules` treats every rule's `.apply()` as
a call that can fail, isolates it, and keeps the other 30 files' unrelated fixes intact
instead of discarding a whole real end-to-end run over one bad assumption in one rule."

---

## D23 — `plugboard` needs `uv`-aware install; not chasing it further tonight

**Alternatives:** switch the sandbox to `uv sync --group test` (installing `uv` into the
image) and keep iterating on this repo until it goes green.

**Why:** with D21 (python_version, workspace member) and D22 (crash isolation) both fixed,
T1 ran cleanly end to end (12 real edits, `status=done`, no crash) — but every test run
still produced no JSON report at all. Reproduced the container run directly (same pattern
as D21's Docker-build reproduction) and got the real cause instead of the generic "crashed
or OOM" message: `tests/conftest.py` fails to import with `ModuleNotFoundError: No module
named 'pytest_asyncio'`, which aborts pytest before the json-report plugin's session hooks
ever fire — not a resource crash, a missing dependency.

Checked why: `pytest-asyncio` (and the rest of plugboard's real test dependencies —
`pytest-cases`, `pytest-env`, `moto[server]`, `ray`, `redis`, `respx`, `time-machine`,
`llama-index-core`, ...) are declared under `[dependency-groups] test = [...]` (PEP 735),
NOT `[project.optional-dependencies]`. `pip install -e .[test]` only understands the
latter — plugboard has no `test` extra there at all, so the install silently installs
nothing beyond the base package; the ONLY reason `pytest` itself exists in the container is
the sandbox's own unconditional `pip install pytest pytest-json-report` step.

Not fixing this tonight: getting `plugboard` green needs `uv sync --group test` (dependency
groups are a uv/PEP-735 mechanism plain pip can't read), which means adding `uv` to the
Dockerfile template as a second install pathway — and even then, several of these
dependencies (`moto[server]`, `ray`, `redis`) suggest integration tests that may need live
services this sandbox's `--network none` isolation (phase-2-sandbox.md) deliberately
forbids. That's a real, separate size of work, not a one-line manifest fix like D21. The
`madkote/fastapi-plugins` result (D19/D20: 22/23, one correctly-classified T2 gap) already
demonstrates T1-only close to its ceiling on a real repo; sinking more time into a SECOND
repo's install plumbing for the same acceptance line item has diminishing return tonight.

**Interview:** "Two real end-to-end repos taught two different lessons about corpus
curation. `fastapi-plugins` needed dependency fixes I could patch in Dockerfile steps.
`plugboard` needed a different PACKAGE MANAGER's install semantics entirely — its test
deps are declared with PEP 735 dependency groups, which plain pip silently ignores rather
than erroring on, so the failure looks like a crash until you actually read pytest's own
stderr instead of trusting the wrapped subprocess result. I didn't chase it to green
tonight because the fix is a different shape of work (a second install pathway, plus
network-isolation questions for its integration tests) than what's already been proven —
I'd rather log that honestly as scope for corpus curation than force a two-line patch that
doesn't actually address the real gap."

---

## D24 — T2 gets a real ModelClient (Gemini, not Anthropic), and a second crash-isolation fix

**Alternatives:** keep T2/repair permanently gated behind "no ANTHROPIC_API_KEY available,"
as it had been since Phase 3 started; or wait specifically for an Anthropic key.

**Why:** two third-party keys were tried to unblock T2 without an `ANTHROPIC_API_KEY`.
`aimlapi.com` (an OpenAI-compatible proxy that also lists Claude model strings) returned
HTTP 403 `insufficient credits` — the key authenticates, the account has no funds, so it's
documented but unusable. A Gemini API key worked end to end: `GET
.../v1beta/models?key=...` returned 200 with a real model list, and a real
`generateContent` call against `gemini-3.6-flash` returned real text and usage metadata.
`gemini-2.5-flash` (the model this key's own model-list called out as available) is
actually retired for new accounts as of this key's tier — the list-models response doesn't
reflect that, only an actual generation call surfaces it, which is why this was verified by
calling the endpoint rather than trusting the catalog. Pricing ($0.75/1M input, $3.75/1M
output, thinking tokens billed at the output rate) was pulled from Google's own pricing page
rather than estimated, since a wrong number would silently corrupt this project's own cost
metric (PLAN.md §7).

Built `GeminiModelClient` (`agent/model_client.py`) as a plain `requests`-based
implementation of the existing `ModelClient` Protocol — no SDK dependency, matching the
same call already made for `corpus/github_client.py`. One real behavior it has to handle
that `FakeModelClient` never could: with too small a `max_output_tokens`, the model spends
its entire budget on internal "thinking" tokens and returns `content: {}` — a real HTTP 200
with nothing usable in it. Reproduced live during testing, not assumed. `complete()` raises
`GeminiEmptyResponseError` in that case rather than returning `text=""`, since a silent
empty string would let `repair()` build a diff out of nothing.

Wiring in the first ModelClient that can genuinely fail (network error, quota, this empty-
response case) surfaced the exact D22 gap one layer up: `agent/graph.py`'s `repair()` node
had zero exception handling around `model_client.complete()`, and the `repair -> run_tests`
edge was unconditional — a real failure there would have crashed `.invoke()` exactly the
way an unguarded codemod rule did before D22. `FakeModelClient` can't raise by construction,
so this was invisible until a client that actually talks to a network existed. Fixed the
same way as D22: `repair()` now catches the exception, logs it, and returns
`status="failed"`; the `repair` node's outgoing edge is now conditional
(`route_after_repair`) on that status rather than hardwired to `run_tests`.

**Interview:** "Getting a real model client wired in didn't just unblock T2 — it found a
second instance of the exact class of bug D22 already fixed, in a part of the graph that
looked safe purely because its only tester so far couldn't fail. `FakeModelClient` is a
perfectly good routing-logic tester, but its assumption — that `.complete()` always returns
— stopped being true the moment a real network call was behind it. The fix is the same
shape as before: treat every external boundary as something that can fail, and make sure
the graph has a real state for that (`status='failed'` already existed; it just wasn't
reachable), rather than assuming success and letting an exception fall through
`.invoke()`."

---

## D25 — T2 diff application: full-file rewrite + computed diff, not a model-emitted diff

**Alternatives:** ask the model to emit a unified diff directly and feed it straight to
`apply_patch`; use graph-retrieved context (`search_symbol`/`get_dependents`) to find the
repair target instead of parsing tracebacks; support multi-file edits in one repair attempt.

**Why:** `repair()` previously called the model and spent budget on the attempt but never
did anything with the response (docs/interfaces.md flagged this gap explicitly after D24).
Closing it needed three real design decisions, each made against actual failure shapes
this project already hit, not hypothetical ones:

1. **Target-file identification has two genuinely different real shapes.** A crash INSIDE
   first-party code (D19's `PydanticImportError` at class-body evaluation time) puts the
   right file directly in the traceback — take the deepest first-party, non-test path
   before the trace drops into a third-party frame. But a `pydantic.ValidationError` raised
   at INSTANTIATION (D20's `RedisSettings`/`LoggingSettings` case — the more common T2
   target per PLAN.md's own framing) does NOT: the traceback only shows the call site
   (often a test file, excluded by I1) and pydantic internals: the class needing the fix is
   never mentioned as a path. Pydantic's own message names it directly ("N validation
   errors for ClassName"), so the fallback greps the repo for that class's definition
   instead of trusting the traceback's path list. `agent/repair.py`'s two strategies exist
   because one heuristic doesn't cover both real cases.

2. **Ask for the corrected full file, then compute the diff ourselves** via the
   already-existing, already-tested `make_unified_diff` — not ask the model to emit a
   unified diff. LLM-generated diffs are a well-known failure source (hunk line-count
   mismatches, fuzzy-context application misses); this reuses a tested utility and means
   the ONLY way `apply_patch` can reject a T2 edit is a genuine I1-I3 violation or a real
   syntax error, not a malformed diff. Costs more output tokens than a diff would.

3. **No graph-retrieved context, single-file only.** `CodeGraph`'s `search_symbol`/
   `get_dependents`/`get_dependencies` were never wired into the live loop — `CodeGraph` is
   only used once, upstream, to build the initial `work_list`. Wiring live graph queries
   into `repair()` is a separate integration; PLAN.md itself frames "graph vs. embedding vs.
   whole-file-dump retrieval" as an ablation to MEASURE later, not a prerequisite for T2 to
   exist. T2's actual failure classes (implicit-Optional, coercion strictness, custom
   validators) are typically localized to one file anyway.

A connected fix, found while building this rather than assumed: `route()`'s no-progress
signature was computed from `_failing_node_ids(outcomes)` alone. Collection errors are NOT
`TestOutcome`s (`results.py` keeps them separate) and can be the ONLY failure signal at all
— exactly the state a fresh migration starts in (0 outcomes recorded, everything blocked at
collection, as D19/D20's own runs showed). With `failing` permanently `[]` in that state,
`no_progress.observe([])` would hash the same empty signature every call and falsely
declare no-progress after `repeat_threshold` attempts regardless of whether repair was
actually reducing the number of collection errors. Fixed by folding `run.collection_errors`
into the same signature `no_progress.observe()` sees. `repair()` itself has the matching
fix: it now scans `collection_errors` too (`repair.collect_failure_texts`), not just
outcome-level failures, so it can actually attempt a repair in that starting state instead
of returning `{}` every time because `_failing_node_ids` found nothing.

Also moved the system prompt to `agent/prompts/repair_system.md` — the previous stub inlined
it as a literal string in `graph.py`, which is exactly what CLAUDE.md's "prompts live in
`agent/prompts/*.md`, never inline in Python" convention exists to prevent; fixed it while
building the real version rather than carrying the debt forward.

**Interview:** "The two target-identification strategies aren't speculative coverage — one
maps to a bug I actually fixed in this project (D19) and the other maps to the bug I found
right after it (D20), and they need genuinely different signals: one is 'read the file path
out of the crash,' the other is 'read the class name out of pydantic's own error message and
go find where it's defined,' because a validation error's traceback never shows you the
class body that's actually wrong. I also chose to have the model rewrite the whole file
rather than emit a diff, specifically to keep 'did T2 produce a real code change' and 'is
that change safe to apply' as two separately-answerable questions — the diffing is
deterministic and already tested, so the only way an edit gets rejected is a genuine
invariant violation, not a formatting mismatch in what the model wrote."

---

## D26 — Four real bugs from the first live T1+T2 run, plus one confirmed known limit

**Alternatives:** ship D25's T2 build as-is and call it verified once the mocked unit tests
passed; treat the single-file-scope limitation as resolved by expanding to multi-file edits
immediately.

**Why:** running the full T1+T2 loop for real (Gemini, live Docker) against
`madkote/fastapi-plugins`, repeatedly, surfaced four distinct, real bugs — none visible from
`FakeModelClient`-based tests, all found by watching actual runs disagree with each other or
with expectations:

1. **No `temperature` set at all.** Two back-to-back runs against the identical repo state
   produced different outcomes — one successfully fixed `fastapi_plugins/memcached.py`, the
   other didn't touch it. PLAN.md's own invariant I6 ("every scored run is reproducible...
   temperature 0") already existed specifically to rule this out; `GeminiModelClient` simply
   never set it. Fixed: `generationConfig.temperature = 0`.

2. **`agent.repair_rejected` carried empty `violations` and no diagnostic at all.** A run
   produced a rejection with zero I1-I3 violations — meaning the real reason (a `git apply`
   or post-apply syntax failure) was sitting in `PatchResult.stderr`, which the log line
   never included. An undiagnosable rejection is a silent-failure path CLAUDE.md's own
   review checklist calls out; fixed by adding `stderr` to the log line.

3. **Repair targeted a file no code change could ever fix.** `fastapi_plugins/memcached.py`
   kept getting "fixed" because its traceback has a genuine first-party frame — a
   deliberate `raise RuntimeError('aiomcache is not installed')` guard — sitting right next
   to a `ModuleNotFoundError` for a package that was simply never installed (the exact
   `aiomcache` gap already tracked in D20/D23, `FailureClass.THIRD_PARTY_PIN` per
   interfaces.md §6). `extract_target_file` had no way to tell "the file itself is buggy"
   from "the file correctly detected a missing dependency and said so." Fixed: failure
   texts matching `ModuleNotFoundError: No module named` are filtered out before either
   target-identification strategy runs, so repair stops wasting real money "fixing" files
   that were never broken and correctly moves on to a failure it might actually help with.

4. **`max_output_tokens=4096` (the original guess) wasn't enough.** Once (3) stopped
   misdirecting repair at `memcached.py`, it correctly targeted `demo.py` (321 lines) for
   the real `AppSettings`/`RedisSettings` validation failure — and got `repair_no_edit`
   twice: no parseable code block. Repair asks for the WHOLE corrected file, not a diff
   (D25), so the budget has to cover thinking tokens AND a full file that size. Raised to
   32768; both subsequent attempts produced a clean, applying rewrite (5892 and then 11975
   output tokens — confirming the original guess was the actual bottleneck, not a one-off).

With all four fixed, repair reliably applies syntactically valid, invariant-clean rewrites
to `demo.py` — but the underlying test still fails, the exact same way, every time. This is
the ONE limitation named explicitly when D25 proposed this design ("single-file edits only
... multi-file semantic edits are out of scope"), now confirmed empirically rather than
hypothesized: `redis_url`/`redis_user`/etc. are fields on `RedisSettings`
(`fastapi_plugins/_redis.py`), and `demo.py`'s `AppSettings` only composes/inherits it — no
rewrite of the file named in the error can fix a field declared in a DIFFERENT file. Not
fixing this now: multi-file repair needs identifying and editing a dependency graph of
files in one attempt, a materially bigger scope than this cut, and PLAN.md itself treats
richer retrieval as an ablation to measure later, not a T2 launch requirement.

**Interview:** "The first live run of a brand-new pipeline component doing four different
things wrong wasn't a bad sign — every one of those four was invisible to the tests I'd
already written, because they only exercise the code paths I anticipated. Two are
correctness bugs a real model call was uniquely positioned to surface (non-determinism,
insufficient token budget); one is an observability gap (an undiagnosable rejection); one
is a genuine failure-taxonomy gap (treating 'this file correctly reported a missing
dependency' the same as 'this file has a bug'). What's left after fixing all four isn't a
bug — it's the actual, load-bearing single-file-scope limitation I named up front, now
backed by a real repro instead of a guess."

---

## D27 — Five real infra bugs unblocking `plugboard`, and where it actually stops

**Alternatives:** give up on `plugboard` after D23's original diagnosis (needs `uv`); or
keep patching indefinitely until it goes green.

**Why:** trying to unblock `plugboard-dev/plugboard` — a much larger, more realistic
corpus repo (32 migration units vs. `fastapi-plugins`' handful) — surfaced five distinct,
real infrastructure bugs, each found by reproducing a failure directly against a live
daemon rather than guessing:

1. **Docker builds defaulted to the host's native arch.** This Mac is Apple Silicon
   (arm64); `docker build` with no `--platform` flag builds natively. `plugboard`'s
   `uv.lock` pins `greenlet==3.4.0`, which ships zero Linux ARM64 wheels (only
   x86_64/musllinux/macOS/Windows) — a build that would behave differently depending on
   who ran it, exactly what PLAN.md's I6 exists to prevent. Fixed: `--platform linux/amd64`
   pinned explicitly on both `docker build` and `docker run` (`sandbox/policy.py`,
   `BUILD_PLATFORM`), folded into `compute_deps_hash` so old wrong-platform cached images
   don't keep matching their tag.
2. **`uv sync` installs into an isolated `.venv`, not the system Python.** The existing
   pydantic-pin step (`pip install --force-reinstall`) would "succeed" while pinning a
   Python `uv run pytest` never uses. Fixed: `_venv_install_cmd` detects `install_cmd[0]
   == "uv"` and targets `/repo-base/.venv/bin/python` explicitly via `uv pip install
   --python`.
3. **Same gap, missed on the first pass, for the sandbox's own tooling.** `pytest`/
   `pytest-json-report` were installed via system pip unconditionally — invisible to `uv
   run` for the same reason as (2), so pytest rejected `--json-report` as unrecognized.
   Fixed by routing through the same `_venv_install_cmd` helper, reordered to run AFTER
   `{install_cmd}` (the venv doesn't exist until `uv sync` creates it).
4. **`uv run`'s cache write failed under the read-only sandbox root.** The container runs
   as `--user nobody` with `--read-only`; `uv run` tries to write its cache under
   `$HOME/.cache/uv`, and `nobody`'s `$HOME` is `/nonexistent`. Fixed: `--no-cache` (skip
   caching) combined with `--no-sync` (skip uv's own re-verification against
   `pyproject.toml`/`uv.lock`, which would otherwise try to fetch a package over the
   network during the network-isolated test-run phase) in `test_cmd`.
5. **The `/repo` tmpfs (half of `SandboxPolicy.memory_mb`) was too small for the
   `.venv`.** `plugboard`'s test deps include `ray[default,tune]`, `pandas`,
   `llama-index-core` — a demo run at `memory_mb=1024` gave only 512MB, and the
   entrypoint's `cp -r /repo-base/. /repo/` silently failed mid-copy with "No space left
   on device" (a `cp` warning, not a fatal container exit — pytest then ran against a
   half-copied venv and found nothing). Not a code defect (`SandboxPolicy.memory_mb`
   already defaults to 4096, not 1024 — the demo script had overridden it down for the
   much smaller `fastapi-plugins`); fixed by using a larger budget for this repo.

With all five fixed, the image builds, `uv sync` resolves the workspace correctly, and
`pytest` collects all 392 tests. But a full run hangs: `tests/unit/test_channel.py::
test_channel[AsyncioConnector]` — a UNIT test, not one of the `tests/integration/`-named
ones — never completes, confirmed by watching it live (started, no PASS/FAIL, still
running after 150s with nothing after it). This is a different, deeper problem than 1-5:
those were all "the sandbox is configured wrong for this repo's install/runtime
mechanics"; this is "this repo's async connector tests need something the sandbox's
constraints (`--network none`, restrictive namespaces, QEMU emulation) don't provide,"
much closer to D23's original prediction ("integration tests may need live services this
sandbox's network isolation deliberately forbids") — just manifesting as a hang in a unit
test rather than a clean connection-refused error in an integration one.

Not chasing this further: diagnosing one specific async hang would mean instrumenting
`AsyncioConnector` directly or bisecting pytest-timeout-style per-test, and each iteration
here costs 15-45 real minutes (QEMU emulation plus this repo's dependency weight) — a much
worse cost/information ratio than everything found so far. Two real corpus repos now each
have an independently diagnosed, well-understood reason they don't reach fully green under
this architecture: `fastapi-plugins` needs multi-file T2 repair (D26); `plugboard` needs
either test-suite-level changes (skip/mark the hanging tests) or sandbox changes this
project doesn't have a clear design for yet (looser network isolation specifically for
loopback pub/sub, or a different concurrency model under QEMU).

**Interview:** "Five bugs in a row on one repo sounds bad until you look at what kind they
were — every one was 'the sandbox is misconfigured for this repo's install or runtime
mechanics,' and each was fixable in isolation with a live repro. The sixth issue is a
different kind entirely: an async test hanging under network isolation isn't a
misconfiguration, it's evidence that this repo's tests assume a network primitive my
sandbox's threat model deliberately removes. I stopped there because that's a real design
question — how much network do 'unit' tests get to assume — not a bug I can just patch
my way through, and two independently-diagnosed real repos each falling short for a
different, well-understood reason is more honest data than one lucky green run would be."

---

## D28 — T2 becomes multi-file: base classes, not just the file named in the error

**Alternatives:** wire real graph-retrieved context (`search_symbol`/`get_dependents`) to
find related files via full import resolution; keep T2 single-file and treat this class of
failure as permanently out of scope.

**Why:** D25/D26 confirmed the exact gap empirically: `fastapi_plugins/demo.py`'s
`AppSettings` inherits `fastapi_plugins.RedisSettings`, and the fields actually causing the
`ValidationError` (`redis_url`, `redis_user`, ...) are declared on `RedisSettings` in
`fastapi_plugins/_redis.py`, not in `demo.py` at all — confirmed by reading the real source,
not inferred. `demo.py` itself declares zero fields related to the failure. No single-file
rewrite of the file an error names can fix a field declared on a base class in a different
file.

Chose a local, LibCST-based heuristic (`repair._base_class_names`) over full import
resolution: walk the target file's top-level `ClassDef` nodes, collect
base-class names (qualified names reduced to their final component —
`fastapi_plugins.RedisSettings` -> `RedisSettings`), exclude well-known pydantic/stdlib
bases (`BaseModel`, `BaseSettings`, `object`), then grep the repo for where each remaining
name is actually defined (reusing the exact same class-definition search
`extract_target_file`'s strategy 2 already does, now factored into a shared
`_find_class_definitions` helper). Rejected wiring real graph-retrieved context: `CodeGraph`
was never wired into the live loop at all (D25 already made this call for the single-file
case) — full import resolution answers a more general question than this needs, and
PLAN.md's own ablation framing ("graph vs. embedding vs. whole-file-dump retrieval") treats
richer retrieval as something to measure later, not a prerequisite. A name-based heuristic
that reuses code already proven against real corpus tracebacks is more consistent with the
size of problem this actually is.

The rest of the pipeline generalizes cleanly from "one file" to "one or more files" without
new concepts: `build_repair_prompt` takes a `dict[path, content]` instead of one path/before
pair; the system prompt tells the model to inspect every file it's given (not just the
first) and to emit one `File: <path>` + fenced block per file that actually needs a change;
`extract_rewritten_files` returns a `dict[path, content]` instead of a single optional
string; `repair()` loops over that dict, computing and applying a diff per file through the
SAME `apply_patch` chokepoint T1 and single-file T2 already used — no new invariant-
enforcement code needed, which is exactly the payoff of having that chokepoint at all. A
model-named path never shown as context is logged and ignored rather than trusted blindly
(`agent.repair_unknown_path`) — nothing lets the model write to a file it wasn't given.

**Interview:** "The single-file design wasn't wrong, it was scoped — I said as much when I
proposed it. What made multi-file tractable without a redesign is that the actual NEW piece
is small: find base classes by name and grep for their definition, reusing code already
proven against a real corpus bug. Everything downstream — building the prompt, parsing the
response, computing the diff, applying it through the invariant chokepoint — was already
written to work per-file; multi-file is just calling that once per file instead of once,
total. That's the benefit of having a chokepoint in the first place: extending WHAT feeds it
doesn't mean touching HOW it enforces anything."

---

## D29 — Multi-file T2 confirmed live; "fully green" is provably unreachable for this repo

**Alternatives:** keep chasing `madkote/fastapi-plugins` toward 100% (e.g. by loosening
network isolation for a live redis/memcached, or relaxing I1 for this one file).

**Why:** the D28 multi-file build was run live, three times. All three reproduced the same
real capability: `edit_t1` + `repair()` correctly found `demo.py`'s `AppSettings`, walked its
base classes, and fixed the ACTUAL broken files (`fastapi_plugins/_redis.py`,
`fastapi_plugins/logger.py`, and in later rounds `plugin.py`/`control.py`/`memcached.py` as
different failures surfaced first) — never `demo.py` itself, which needed no changes. One
run hit a transient Gemini read-timeout on a later repair attempt; `repair()`'s D24
exception handling caught it and reported `status="failed"` cleanly, no crash. Collection
errors dropped from 4 to 2 (both the pre-existing, already-tracked `aiomcache` gap, D20/D23)
and the unscoped pass count rose from 22/23 to 30/48 — more test modules could even collect
once the real bugs were fixed. This is the strongest evidence yet that T2's actual "semantic
edit" capability (not just the plumbing around it) works against a real corpus repo.

Installed `aiomcache` (a one-line `setup_overrides` addition, same pattern as this repo's
existing `httpx` override) to close the last tracked collection-error gap and see the
full picture. Two things this fix surfaced, closing out the investigation rather than
opening a new one:

1. **Memcached tests need a live memcached server**, exactly like the Redis tests need a
   live Redis server (`MemcachedError: ... RetryError ... OSError` — a connection failure,
   not a pydantic issue). Same class of barrier, no code rewrite fixes it.
2. **`tests/test_control.py` itself still uses `pydantic.BaseSettings`** as a type
   annotation (`class DummyPluginHealthOK(...): config: pydantic.BaseSettings=None`) — a
   real, unmigrated v1 usage. But it's a TEST FILE. I1 ("the agent may never edit test
   files") correctly, permanently refuses to touch it. This is not a gap in T1 or T2's
   capability — it's invariant enforcement doing exactly its job.

Given both, "fully green" is not an achievable target for THIS repo by any source-editing
agent that respects I1 and doesn't provision live infrastructure — not a limitation of this
implementation, a structural fact about the repo. The migration itself — the actual pydantic
v1→v2 code changes — is, as far as this investigation can tell, complete and correct: every
remaining red test fails for a reason with nothing to do with pydantic. Not chasing this
further: loosening network isolation for one repo's tests, or relaxing I1 for one file,
would both be trading a real invariant for a single green checkmark — precisely the kind of
metric-gaming CLAUDE.md's invariants exist to prevent, and PLAN.md's I4 (only baseline-
passing tests count) already gives the honest way to handle it: these tests should be
excluded from the scored denominator, not "fixed" by weakening what's enforced.

**Interview:** "The most interesting result here isn't that the agent got closer to green —
it's that I can now PROVE it can't get all the way there, and exactly why. Two of the
remaining failures need live infrastructure my sandbox deliberately doesn't provide, and one
needs editing a test file my agent is built to never touch. Both are the invariants working
correctly, not bugs. That's actually the more defensible position for a scored evaluation:
a raw pass rate that quietly excluded or fixed those would be lying about what the agent
did; knowing precisely which failures are structurally out of scope is what makes the
number honest, which is exactly I4's whole point."

**Addendum — confirmed with real baseline data, not just pattern-matching (D30's baseline
capture run):** the v1 baseline for this repo collects 80 tests; 24 already fail at v1,
before any migration touches anything — every `test_memcached.py`/`test_redis.py` test
(connection-refused, no live service) plus one `test_control.py::test_router[...]` case
downstream of the same missing services. Per I4, these 24 were never a valid part of the
scoring denominator in the first place; the "22/23" and "30/48" numbers reported earlier in
D19/D20/D29 measure something real (mechanical progress against the raw test count) but
overstate the actual gap, since roughly 30% of this repo's tests were categorically
unwinnable from the start. This doesn't change D29's conclusion (100% is still unreachable —
`tests/test_control.py`'s I1-protected `pydantic.BaseSettings` usage is a real, separate
migration bug, not a live-service issue) but replaces an inference with a number: of the 56
tests that legitimately count, the only unfixable failures are the ones gated behind that
one file's collection error.

---

## D30 — `capture_baselines.main()` silently deleted the whole hand-curated manifest

**Alternatives:** leave the destructive behavior and just be careful never to run it against
a manifest worth keeping; require a `--dry-run`/confirmation flag before any save.

**Why:** trying to apply PLAN.md's I4 invariant honestly — checking whether the corpus's
fastapi-plugins/redis/memcached test failures also failed at the v1 BASELINE, which would
make them legitimately excludable from the scored denominator rather than "unreached
failures" — meant actually running `capture_baselines.py` for the first time (its own
docstring already flagged that Docker hadn't been available when it was written, so it had
never run end to end). It did what it was supposed to: it correctly identified
`fastapi-plugins`'s v1 baseline pass rate as 70%, below Phase 0's own 80% quality gate. What
it did NEXT was the real bug: `main()` built `updated` by appending only the specs that
PASSED this run's capture, then called `save_manifest(updated, manifest_path)` — an
unconditional overwrite. Both corpus repos failed on this particular run (`plugboard` for
an unrelated, already-known reason — this standalone script's own Dockerfile template never
learned about `uv`, D21/D27's fixes live in `sandbox/image.py`, a different template
entirely) — so `updated` ended up empty, and `corpus/manifest.json` — a file its own
`RepoSpec` docstring calls "hand-curated and committed" — went from two real, working,
carefully-fixed entries to `[]` in one command, with no confirmation and no dry-run option.

Recovered by reconstructing both entries from this session's own record (their exact JSON
had been printed multiple times just before this happened) — not from git, since the file
had never actually been committed with real content at any point (`git show HEAD:...` is
also `[]`), so there was no tracked history to fall back on. That gap is itself worth
naming: an ungitted, auto-regenerated file that a script can silently empty is exactly the
shape of thing that's fine right up until the one time it isn't.

Fixed the actual bug: `capture_baselines.py`'s `main()` now appends the ORIGINAL spec
(baseline left unchanged, usually still `None`) whenever this run's capture or sanity check
fails, instead of omitting it — a repo failing baseline capture on one particular invocation
(a network hiccup, a transient service outage) is not the same event as a human deciding to
drop it from the corpus, and conflating the two is what caused the loss. This brings
`capture_baselines.py` in line with a safety pattern `validate.py`'s own `main()` already
used correctly the whole time (`save_manifest(load_manifest(manifest_path) + new, ...)` —
additive-only, never a destructive overwrite) — `capture_baselines.py` was the one
inconsistent with the project's own established pattern, not the other way around.

**Interview:** "I found a real, previously-latent bug the way you'd want to: not by
inspection, but by being the first person to actually run the code against real data, on
a newly-available Docker daemon its own docstring said hadn't been possible before. The
telling detail isn't that a script had a bug — it's that fixing it meant noticing an
inconsistency between two files: `validate.py` already treated the manifest as
append-only, and `capture_baselines.py` didn't, for no principled reason. That's the kind
of thing that's easy to miss reading either file alone and obvious once you're forced to
compare their actual behavior against real, destructible data."

---

## D31 — `capture_baselines.py`'s own Dockerfile had silently drifted out of date

**Alternatives:** patch `capture_baselines.py`'s separate Dockerfile template in place
(re-add its own copy of the `uv`/pydantic-settings fixes); leave it broken for `uv` repos
since it's "only" a Phase 0 tool.

**Why:** wanted to run `capture_baselines.py` against `plugboard` to see whether its
async-connector hang (D27) also occurs at the v1 baseline (which would mean it's unrelated
to the migration at all) — and it failed immediately, because this script's Dockerfile
template still only knew `pip install pytest pytest-json-report "pydantic{constraint}"`.
Every fix `sandbox/image.py` picked up from real corpus runs — `uv`-aware installation
(D27: a `uv sync` repo's `.venv` is invisible to plain `pip install`), the
`pydantic-settings` extra package (D20: needed the moment any real migration moves
`BaseSettings`), and the `--platform` pin (D27: builds must not depend on the host's native
arch) — had been made ONLY in `sandbox/image.py`, and never ported to this script's own,
separate copy of the same logic. The module's own docstring had already predicted this
exact failure mode: "when Phase 2 builds the real sandbox... this script's build-image logic
is the thing to fold into it" — Phase 2 has existed the whole time this session was finding
these fixes; nothing had folded them in yet.

Fixed by exporting the install-ecosystem helpers `sandbox/image.py` already had
(`pydantic_constraint`, `extra_packages`, `venv_install_cmd`, `sandbox_tools_cmd`,
`pydantic_pin_cmd` — dropped their leading underscores, since they're genuinely shared
utilities now, not module-private) and having `capture_baselines.py` import and reuse them
directly, rather than reimplementing the same logic a second time. Did NOT fully unify the
two Dockerfile-building flows into one function: `capture_baselines.py` builds at TWO shas
(`pre_sha` under v1, `post_sha` under v2 for the human-migration sanity check) where
`sandbox/image.py`'s public `build_image`/`image_tag`/`render_dockerfile` are hardwired to
`pre_sha` alone by design — extending that stable, already-tested public interface to accept
an arbitrary sha for the sake of one Phase-0 caller's edge case would have been a bigger,
riskier change than the actual problem warranted. Sharing the REUSABLE PIECES (the
ecosystem-detection logic) without merging the two DIFFERENT PIECES (what sha to build,
whether to cache by tag) is the more precise fix for what was actually duplicated.

**Interview:** "This is what 'shared logic living in two places' costs in practice: three
real fixes landed in one file and a second file kept silently failing the exact same way,
because nothing forced them to agree. I didn't discover this by code review — I found it by
trying to actually use the second file for the first time in months, on a repo that needed
exactly the fix the first file already had. The corrective isn't 'always fully unify
everything that looks similar' — the two scripts genuinely build different things (one sha
vs. two, cached vs. not) — it's 'extract the piece that's ACTUALLY the same and share only
that,' which is a narrower, safer refactor than merging the whole module."

---

## D32 — `plugboard`'s `pre_sha` isn't a valid v1 baseline; drop it from the corpus

**Alternatives:** keep chasing the async-connector hang (D27) as if it were the blocking
issue; try a different pre_sha further back in `plugboard`'s history.

**Why:** with D31's fixes landed, `capture_baselines.py` finally got past the build stage
for `plugboard` and failed at the TEST stage instead — fast (~40s, not the ~10-minute
async-connector hang from D27), with "no json report — likely a collection error."
Reproducing directly (same pattern as every other real bug this session) showed the actual
cause has nothing to do with the sandbox at all:

```
plugboard-schemas/plugboard_schemas/component.py:6: in <module>
    from pydantic import Field, field_validator
E   ImportError: cannot import name 'field_validator' from 'pydantic'
```

`field_validator` is a pydantic v2-ONLY API (v1's equivalent is `@validator`). This import
sits in `plugboard-schemas` — a separate package inside the same `uv` workspace, extracted
in its own commit (`fd99eb3`, "Configure uv workspace and extract plugboard-schemas
package") — and it's already there at `pre_sha`, the commit `validate.py`'s discovery
heuristic identified as "immediately before the migration." That means `pre_sha` does NOT
represent a genuine pre-migration state for this repo at all: the `plugboard-schemas`
sub-package had already independently moved to pydantic v2 syntax before the commit Phase 0
picked as the migration boundary. Forcing pydantic v1 into this environment (exactly what a
baseline capture is supposed to do) can't even IMPORT the codebase, because part of it
already requires v2.

This retroactively answers the D27 question ("does the async-connector hang also occur at
v1 baseline?") by making it moot — there's no valid v1 baseline for this repo to check it
against. It also reframes everything since D21: the five real infra fixes (D21, D27) were
all necessary and correctly diagnosed, but they were fixing the WRONG problem's symptoms —
no amount of sandbox tooling can produce a valid "before" state for a repo whose identified
migration commit doesn't actually capture where the migration started. This is a genuine gap
in Phase 0's corpus-curation methodology, not this repo's fault or this session's tooling:
`validate.py`'s commit-search heuristic finds A commit that touches dependency files and
pydantic-shaped diffs, but has no way to verify that EVERY part of a multi-package workspace
was still on v1 immediately before it — a single-package repo can't have this problem, a
workspace repo with independently-migrated sub-packages can.

Recommending `plugboard-dev/plugboard` be dropped from the corpus rather than chased
further: fixing this would mean walking back through the repo's history to find a genuinely
clean v1 boundary across ALL workspace members simultaneously (if one exists at all), which
is Phase 0 discovery work, not a sandbox or agent fix. `madkote/fastapi-plugins` remains the
corpus's one real, working, fully-characterized dev-split example (D19-D29).

**Interview:** "Five real fixes in a row on one repo and I still couldn't get a clean
baseline — that pattern was worth noticing, not just powering through. The sixth issue
wasn't a sixth infra bug, it was proof the first five were fixing symptoms of a problem
one layer up: my corpus discovery step verified there's A migration commit, but never
verified the whole workspace was uniformly pre-migration right before it. For a monorepo
where sub-packages can migrate on independent timelines, that's not a safe assumption —
and finding that out required actually trying to build a v1 baseline, not reading the
commit diff and assuming it was representative."

---

## D33 — Hardening `validate.py` with what `plugboard` taught: two real fixes

**Alternatives:** leave `validate.py` as-is and rely on `capture_baselines.py`'s Docker-
dependent baseline capture to catch a repeat of D32's problem (as it did, eventually);
combine multiple commit-search strategies with AND instead of trying them independently.

**Why:** with the corpus down to one repo after dropping `plugboard`, expanding it again
meant first fixing the two real gaps that discovery/validation run had exposed:

1. **The commit-location heuristic was too narrow.** The last real discovery run dropped 36
   of 46 candidates at "could not locate a migration commit" — `_find_migration_commit`
   required the commit MESSAGE to mention "pydantic" + "v2" AND the diff to touch a
   dependency file with a pydantic-related change, combined with AND. Real migrations don't
   reliably phrase commit messages a specific way, and a repo may bump its dependency file
   in an earlier, separate commit from the one that rewrites the source. Fixed by trying
   several independent strategies in order of specificity instead of one combined query —
   the two pickaxe fallbacks (`git log -S field_validator`, `-S "ConfigDict("`) find the
   commit that changed whether a v2-only symbol exists in the tree at all, which doesn't
   depend on commit message wording.
2. **Nothing checked that `pre_sha` was actually a clean v1 state repo-wide.** D32's
   `plugboard` bug — a workspace sub-package already using v2-only syntax before the
   identified migration commit — is exactly the shape of thing a per-commit diff check can
   never catch, because the offending code was never touched by that commit. Added
   `_pre_sha_is_clean_v1`: checks out `pre_sha` and greps the WHOLE tree for known v2-only
   symbols (`field_validator`, `model_validator`, `ConfigDict(`, `model_dump(`,
   `model_config =/:`), dropping the candidate if any are found anywhere. Requires a real
   checkout for every candidate now, not just code-search-sourced ones with no known sha —
   `_clone_shallow` was factored out and is called unconditionally in `validate_candidate`.

Testing this for real (local git repos, no network needed) found a second, genuine bug in
the SAME turn: `_V2_ONLY_SYMBOLS` had unescaped `(` characters in `ConfigDict(`/
`model_dump(`, which is a metacharacter in POSIX extended regex (`-E`). `git grep` exited
128 ("empty (sub)expression") on the malformed pattern — and the check `if result.returncode
== 0 and result.stdout.strip()` treated any non-zero exit (including a broken pattern) the
same as "genuinely no match," silently reporting every candidate as clean. That is precisely
backwards for a function whose entire purpose is catching a subtle contamination case — a
broken check that fails open is worse than no check, because it looks like coverage that
isn't there. Fixed the regex (escaped parens) and the returncode handling (`git grep`'s exit
code is three-valued: 0 = matched, 1 = no match, >=2 = a real error — only 0/1 are legitimate
outcomes; anything else now fails closed, `ok=False`, with the actual stderr surfaced).

**Interview:** "The pattern here is worth naming on its own: I wrote a safety check, and the
check itself had a bug that silently disabled it — the exact failure mode the check existed
to prevent, one layer up. I only caught it because I wrote a real test with an actual local
git repo instead of trusting the implementation, and the test's assertion failed in a way
that pointed straight at 'the function returned true when it should have returned false' —
which is a much more useful failure than 'some mock call didn't happen.' A safety check that
can silently pass regardless of its own internal correctness isn't a safety check; testing
it against real git behavior is what actually makes it one."

**Addendum — re-running `validate` against the same 46 candidates with these fixes:**
`locate_commit` drops nearly halved (36→17), and `pre_sha_not_clean` correctly caught one
NEW plugboard-shaped candidate proactively, before any Docker involvement — real,
measurable pipeline improvement. Still `survived=1, newly_added=0`: the pool of 46
candidates this session already had didn't contain a second valid repo, even under the
improved funnel. Separately, this run surfaced a genuine (different, minor) bug in the same
new code: `-S "ConfigDict("` pickaxe search failed against a partial (`--filter=blob:none`)
clone with a real git error (a promisor-remote blob fetch failure, unrelated to the pattern
itself), and the exception log only recorded "exit status 128" — `str(CalledProcessError)`
never includes stderr unless read explicitly. Added `_subprocess_error_detail()` and used it
at all three of this file's subprocess exception handlers, so a future failure like this is
diagnosable from the log line alone instead of requiring a manual re-run to find out what
actually happened.

---

## D34 — Targeting the v1/v2 BOUNDARY, not generic v2 mentions, actually grew the corpus

**Alternatives:** keep widening the existing generic queries (more pages, more synonyms of
"migrate"/"bump"); relax `validate.py`'s isolation thresholds instead of finding more
candidates.

**Why:** two full validation passes over the same 46 candidates (D19-era discovery, then
again with D33's improved funnel) produced exactly one usable repo both times — the
candidate pool itself was exhausted, not the funnel. `discover.py`'s existing
`CODE_SEARCH_QUERIES` all search for generic v2 syntax presence
(`ConfigDict`/`field_validator`/`pydantic_settings` imports), which says nothing about
whether a repo ever needed a real migration — plenty of code was simply started fresh on
v2. Added two queries targeting the boundary itself instead: `pydantic.v1` (v2's own
compatibility shim — this string cannot appear in a codebase that was never navigating both
APIs deliberately) and `parse_obj` (removed outright in v2, so live usage in current code is
either a repo mid-migration or one that migrated without cleaning every call site).

Result: 103 candidates instead of 46 (the new queries found real, distinct territory), and
running the D33-hardened validator against the full set produced `newly_added=5,
survived=6` — a 6x increase in usable corpus repos from one query change, where the
previous funnel improvement alone (D33, same 46 candidates) found zero new ones. The lesson
generalizes past this one corpus: a discovery signal's SPECIFICITY to the actual event of
interest (a v1→v2 transition, not just v2's existence) matters far more than the sheer
number or breadth of queries thrown at generic search terms.

**Interview:** "Two different levers looked like they should help — a better validation
funnel, and more search queries — and only one of them actually moved the number, which
was worth noticing rather than assuming both mattered equally. Improving `validate.py`
(D33) was still the right thing to do; it made every future run more accurate. But it
couldn't manufacture candidates that were never in the pool to begin with. The queries that
actually worked didn't search harder for the same signal, they searched for a
qualitatively different one — evidence a codebase was navigating BOTH pydantic APIs at
once, not just evidence it currently uses one of them."

---

## D35 — `iscc-core`: T1-only reaches literal 100% (I4-honest) with zero human edits

**Alternatives:** none needed — this is the result, not a design decision to weigh.

**Why:** D34's expanded discovery surfaced `iscc__iscc-core`, and it's the first repo this
session where `capture_baselines.py` succeeded outright: 315 tests passed reproducibly at
the v1 baseline (4 failed, for a reason established below), comfortably past the 80%/15-test
gate, and the human's own post_sha migration stayed green — a genuinely valid corpus member,
confirmed rather than assumed.

Running T1-only against it live: baseline (v2 image, no edits) collected ZERO tests — every
module import-fails on `from pydantic import BaseSettings, Field` in
`iscc_core/options.py`, the exact same `PydanticImportError` shape found repeatedly this
session. `edit_t1` applied exactly ONE edit — `basesettings_import_to_pydantic_settings` +
`config_class_to_configdict` + `dict_to_model_dump`, all to that single file — and the
result: 315/319 passing, zero collection errors. The 4 remaining failures
(`DataURL.from_data() got an unexpected keyword argument 'base64_encode'`, and one
`conformance_selftest` downstream of it) are a THIRD-PARTY library API mismatch with
nothing to do with pydantic. Checked directly against the captured baseline's own `failed`
set: it is the IDENTICAL four tests, verbatim. T1-only's 315/319 is not "close to green with
an explained gap" — under I4 ("only tests that passed on the pre-migration baseline count"),
the honest denominator is 315, and 315/315 pass. This is not a proof of unreachability like
D29's `fastapi-plugins` finding; it is the actual acceptance criterion
(docs/phase-3-loop.md: "one dev-split repo goes from red to fully green with zero human
edits"), met for real, mechanically, at zero cost.

**Interview:** "This is the cleanest possible version of the result this project was built
to produce: a real repo, a real v1 baseline captured and reproducibility-checked before
touching anything, a single deterministic codemod fix, and every test that passed before
migration still passes after — confirmed against the baseline's own recorded failure set,
not assumed from the pass count alone. The four failing tests aren't a caveat I have to
explain away; they're evidence the check is honest, because they're a pre-existing,
unrelated failure the migration correctly left untouched rather than something the pass
rate is quietly excluding."

---

## D36 — Phase 4 triage: rules + grouping + classifier, no LLM fallback yet

**Alternatives:** build the LLM classifier for `UNKNOWN` alongside the rule-based one;
implement all ten `FailureClass` values now; wire directly into `agent/graph.py` in the
same pass.

**Why:** interfaces.md §6 and phase-4-triage.md already had a solid `FailureClass`/
`Diagnosis`/`Classifier` sketch — the job here was building the real thing against it, not
redesigning it. Three real refinements came from actually having a season of Phase 3
corpus runs to check the sketch against, not from guessing:

1. `REMOVED_API`'s documented strategy ("re-run the relevant codemod") is stale. D18 made
   T1 run eagerly, repo-wide, before any test result exists — by the time triage ever
   sees a failure, T1 already tried. A surviving `REMOVED_API` failure means a T1 rule
   gap, not something to re-run; its strategy here is `missing_t1_rule`, a more
   actionable signal than "try again."
2. `THIRD_PARTY_PIN` and `PREEXISTING` already existed ad hoc, in the wrong layer —
   `agent/repair.py`'s `_MODULE_NOT_FOUND` filter (D26) and this session's own manual
   baseline-diffing (D29/D35). Real triage subsumes both; `repair.py`'s filter is left in
   place for now (replacing it is a separate refactor, not required for triage to work).
3. Only classes with REAL evidence from an actual corpus run got a rule:
   `IMPORT_ERROR`/`THIRD_PARTY_PIN`/`VALIDATION_BEHAVIOUR` (D19/D20/D26/D35),
   `CLASS_DEF_ERROR`/`REMOVED_API` (cheap, unambiguous by exception name/attribute even
   without a corpus hit yet). `SERIALIZATION_DIFF`, `ERROR_MESSAGE_DIFF`, and `FLAKY` are
   NOT implemented — inventing a regex for a failure shape never observed would be
   guessing, exactly what phase-4-triage.md's own "every UNKNOWN is a candidate new rule"
   framing argues against. `FLAKY` specifically needs a different signal (the same node
   disagreeing across two `TestRun`s) than a stateless `classify_text(text)` rule can see
   at all — it belongs at the orchestration layer, alongside `NoProgressDetector`, not here.

Found and fixed one real duplication risk WHILE building, not after: `agent/repair.py`'s
target-file traceback parsing and triage's grouping need the exact same "which first-party
file is really responsible" answer. Extracted it into `traceback_utils.py` and had both
callers use it, rather than repeating D31's mistake a third time now that the pattern is
recognized. Same treatment for failure-text collection: `triage/collect.py`'s
`collect_raw_failures` (which keeps each failure's node_id, needed for classification) is
now what `repair.py`'s `collect_failure_texts` (which only ever needed a flat blob) is
built from, not a second independent implementation.

Verified against a REAL `TestRun` (not just hand-built fixtures): re-ran T1 against
`madkote/fastapi-plugins` live and fed the actual result through
`RuleBasedClassifier.classify()`. Correctly classified the real `ValidationError` as
`VALIDATION_BEHAVIOUR` and the real `PydanticImportError` collection error as
`IMPORT_ERROR` (with `node_ids=()`, correctly — a collection error has no specific pytest
node, and the field says so honestly rather than fabricating one). The 5 memcached
`tenacity.AsyncRetrying`/`OSError` failures (needing a live service, D20/D23) correctly
fell to `UNKNOWN` — no rule exists for "needs a live service" yet, and none was invented
speculatively to cover it.

Not done in this pass: wiring `Classifier` into `agent/graph.py`'s `repair()` (state
already has an unpopulated `diagnoses` field waiting for exactly this — deliberately left
for its own change, since it touches a well-tested state machine and deserves to be
checked on its own), a graph-backed `suspect_symbols` lookup (D25/D28 already made this
same "no CodeGraph wiring yet" call for T2), and the LLM fallback for `UNKNOWN` (no
labelled corpus of real unknowns exists yet to build or verify one against — same
"guessing isn't engineering" reasoning as the deferred rules above).

**Interview:** "The valuable part of building this wasn't writing five regexes — it was
noticing that two DIFFERENT modules were both about to independently answer the same
question ('which file does this traceback actually blame'), right after this exact session
already paid the cost of that happening once with `capture_baselines.py`'s Dockerfile. The
other useful signal was what DIDN'T get a rule: the memcached failures are a real,
observed UNKNOWN, and leaving them unclassified rather than inventing a plausible-looking
regex for them is the more honest choice — a rule I can't point to real evidence for is a
guess wearing a classifier's clothes."

---

## D37 — Triage wired into `agent/graph.py`: skip repair on all-`PREEXISTING` failures

**Alternatives:** wire `Diagnosis` into `repair()`'s target-selection too (route each
diagnosis to a distinct strategy implementation); leave `repair()`'s internals untouched
and only use triage for logging/observability.

**Why:** `AgentState.diagnoses` had sat unpopulated since Phase 3 was first scaffolded —
`repair()` explicitly worked off `state.last_run` instead, exactly because triage didn't
exist yet. Wiring it in for real: a new `classify` node runs between `run_tests` and the
existing `route()` conditional edge, calling `RuleBasedClassifier.classify(state.last_run,
state.repo.baseline)` and populating `diagnoses`.

The one behavioral change made to `route()` — not a redesign, one new check — is real and
measurable: previously, ANY raw failure or collection error meant `route()` would try
`repair` whenever `model_client` was set, with no way to tell "a real migration bug" from
"this test already failed before migration touched anything." `route()` now checks whether
EVERY classified diagnosis is `PREEXISTING`; if so, it finalizes (or advances to the next
unit) exactly like the already-fully-green case, without ever calling `repair()`. Verified
live against `iscc-core` (D34/D35's real captured baseline) with a real Gemini client
available and budget to spend: `agent.classify` correctly identified both of the repo's
diagnosis groups as `preexisting`, and the run finished in one iteration —
`usd_spent=0.0000`. Before this change, the identical run would have genuinely spent real
money asking a model to "fix" an unrelated third-party `DataURL` API mismatch (D35) that no
source rewrite could touch.

Deliberately NOT done in this pass: routing `repair()`'s actual target-selection or
prompting through `Diagnosis` (it still uses `collect_failure_texts`/`extract_target_file`
on the raw `TestRun`, unchanged) — `Diagnosis.evidence` is a short (~200 char) snippet for
grouping/display, not the full multi-line traceback `extract_target_file`'s pattern-
matching actually needs, and reconciling that gap (extending `Diagnosis`'s shape, or
re-deriving full text per diagnosis) is a real design question deserving its own change,
not a rider on this one. This pass makes triage answer ONE question well — "is there
anything left worth trying to fix" — rather than a partial answer to a bigger one.

**Interview:** "The smallest version of this integration was also the most valuable one to
ship first: don't touch how repair() decides WHAT to fix, just give the graph a real answer
to WHETHER it should try at all. That one check is directly, measurably load-bearing — I
watched a real run against a real captured baseline skip a repair attempt it would
previously have made, and the cost line printed zero instead of some nonzero number for an
attempt that could never have succeeded anyway. Wiring the richer routing — different
strategies per failure class — is real future work, but it's a second, separable
improvement on top of a first one that already pays for itself."

---

## D38 — `repair()`'s target-selection routed through `Diagnosis`

**Alternatives:** add a `full_text`/`raw_failures` field directly onto `Diagnosis`; keep
`repair()` on `collect_failure_texts`/the raw `TestRun` permanently, using triage only for
the all-`PREEXISTING` skip (D37); route each `FailureClass` to a distinct repair strategy
implementation (a real `Strategy`/`PathPolicy` dispatch, per interfaces.md §6's original
sketch) instead of one shared prompt-and-apply path with a chosen target.

**Why:** D37 deliberately left this gap open — `Diagnosis.evidence` is a ~200-char
snippet, nowhere near enough for `extract_target_file`'s traceback-frame pattern matching,
so `repair()` still worked off every raw failure text flattened together, regardless of
how many distinct root causes were actually present. That's the exact naive shape
docs/phase-3-loop.md described as a placeholder ("group failures naively and hand the
model the trimmed log"), and it means a repair attempt against two unrelated failures (say,
one `IMPORT_ERROR` and one `VALIDATION_BEHAVIOUR`) would dump both into one prompt, when
picking the mechanical one first and fixing it alone is both cheaper and more likely to
actually unblock the other (a bad import can cascade into failures that have nothing to do
with validation semantics at all).

Rejected the field-on-`Diagnosis` alternative: `Diagnosis` is `Classifier.classify()`'s
documented return type (interfaces.md §6) and `structlog`-logged as-is elsewhere in
`classify_node` — growing it to carry full traceback text would make every consumer of
`list[Diagnosis]` pay for data only `repair()` needs. Instead, `triage/grouping.py` gained
`group_raw_failures(...) -> list[GroupedDiagnosis]`, a new type pairing each `Diagnosis`
with the full `RawFailure` tuple it was built from. `classify_and_group` (what
`RuleBasedClassifier.classify()` actually calls) became a one-line wrapper —
`[g.diagnosis for g in group_raw_failures(...)]` — so the `Classifier` Protocol's
contract is unchanged; `group_raw_failures` is the richer entry point for callers, like
`repair()`, that need to act on one specific diagnosis rather than just report it.

`repair()` now: groups the current iteration's raw failures via `group_raw_failures`,
filters out `PREEXISTING` (I4: never a valid scoring target), `THIRD_PARTY_PIN` (D26: no
source rewrite fixes a missing/pinned dependency), and `FLAKY` (by definition not a
rewrite target — the same node just needs re-running, not editing); picks ONE remaining
`GroupedDiagnosis` via a fixed priority order (`_REPAIR_PRIORITY` in `agent/graph.py`:
`IMPORT_ERROR` > `CLASS_DEF_ERROR` > `REMOVED_API` > `VALIDATION_BEHAVIOUR` >
`SERIALIZATION_DIFF` > `ERROR_MESSAGE_DIFF` > `UNKNOWN` — mechanical/high-confidence
classes before ones needing real semantic judgment); and builds the repair prompt from
only that diagnosis's own `RawFailure` texts, not the full failure set. Rejected
per-class strategy dispatch as a separate, bigger change: it's the natural next step once
there's enough per-class fix-rate data to justify different prompting per class, but
today every class still goes through the same single-shot multi-file repair path
(D24/D25/D28) — only WHICH failure text drives that one path changed here.

`agent.repair_applied`/`agent.repair_rejected`/`agent.repair_no_edit` now log `cls` and
`strategy` from the chosen diagnosis — direct raw material for
docs/phase-4-triage.md's "per-class fix-success table" acceptance criterion (not built
yet: no repair run has accumulated enough volume across enough classes to make one
meaningful, but the events now carry what that table would need).

Verified: full test suite (273 tests, including new coverage for `_select_repair_target`'s
priority ordering and a new end-to-end test proving that when both an `IMPORT_ERROR` and a
`VALIDATION_BEHAVIOUR` failure are present in the same run, only the import failure's
traceback text reaches the model) passes; `mypy --strict src/pmigrate` clean; `ruff
check`/`format` clean.

**Interview:** "D37 answered 'should repair even try' — this answers 'given that it
should, which ONE thing should it try to fix, and on what evidence.' I kept `Diagnosis`
itself untouched and introduced a second, richer type instead of bloating the first,
because the Protocol's contract (`classify() -> list[Diagnosis]`) is a promise other code
already relies on, and 'add a field nobody but one caller uses' is exactly the kind of
scope creep the project's own working agreement warns against. The priority order is a
real, statable policy — fix what's cheap and likely to unblock other failures before
reaching for the class that needs a model to reason about behavior — not an arbitrary
tie-break."

---

## D39 — Corpus expansion: captured 3 more baselines, dropped 1 repo, for real reasons

**Alternatives:** loosen `MIN_PASS_FRACTION`/`MIN_PASS_COUNT` to let borderline repos in
as-is; accept `capture_baselines`'s generic drop reasons at face value and move on to
different candidate repos instead of debugging these four.

**Why:** Phase 4's own acceptance criteria (docs/phase-4-triage.md: accuracy on ≥100
hand-labelled real failures, measured pass-rate lift, per-class fix-rate table) need real
failure volume across many repos — the corpus had only 2/6 manifest repos with captured
baselines (411 tests total). Running `capture_baselines` against the other 4 dropped all
4 on the first attempt, with `CalledProcessError.__str__()` giving no real diagnostic for
the Docker build failure (the same observability gap D33 already found and fixed in
`validate.py`, now also present in `capture_baselines.py`) — so each was reproduced by
hand rather than accepted at face value.

All four turned out to be real, distinct root causes, not one systemic bug:
- **`madkote__fastapi-plugins`** (dropped: "pass fraction 0.70 < 0.8"): `tests/test_redis.py`,
  `tests/test_memcached.py`, `tests/test_scheduler.py`, and one `test_control.py` case need
  a live Redis/Memcached service the single-container sandbox never provisions — confirmed
  by reproducing locally (56 passed / 24 errored, the exact 0.70 the real run found).
  Excluded via `test_cmd` (`--ignore`/`--deselect`), not by loosening the gate — the
  remaining 54 tests pass at 100%. This is a real curation choice, not gate-gaming: I4
  already treats "this needs infrastructure the sandbox can't provide" as out of scope
  the same way it treats a pinned third-party dependency (D26).
- **`SupImDos__pydantic-argparse`** (dropped: "0 tests passed reproducibly"): its
  `pyproject.toml` has no `[test]` extra at all — real test deps
  (`pytest-mock`/`pytest-cov`/`covdefaults`) live only in `[tool.hatch.envs.default]`,
  which `pip install -e ".[test]"` has no way to see (pip silently installs nothing extra
  rather than erroring on the missing extra name). Fixed via `setup_overrides`, the exact
  pattern already used for `madkote`'s `httpx`/`aiomcache` — installs the deps directly.
  746/746 pass once fixed.
- **`Aiven-Open__rohmu`** (dropped: "0 tests passed reproducibly"): two independent bugs —
  the real extra is named `[dev]`, not `[test]` (same silent-no-op-on-missing-extra
  behavior as above); and `[dev]` pulls in `python-snappy`, whose C extension needs
  `libsnappy-dev`'s headers, absent from `python:3.11-slim`. Fixed `install_cmd` to
  `.[dev]` and added the apt package via `setup_overrides`. 195/195 pass once both are
  fixed.
- **`COSCUP__COSCUP-Volunteer`** (dropped: Docker build failed at pre_sha, generic exit
  code 1): its `pyproject.toml` declares `[tool.poetry] package-mode = false` — this is an
  application (a volunteer-management web app), not an installable library. `pip install
  -e .` can never succeed at either pydantic version; poetry-core itself refuses
  ("Building a package is not possible in non-package mode"). Not a sandbox bug to fix —
  structurally incompatible with the corpus's install-then-test model. Dropped for real,
  same call as `plugboard` (D32), documented rather than silently removed.

Also fixed the observability gap that made all four drop reasons this uninformative in
the first place: `capture_baselines.py` had the identical `str(CalledProcessError)`-with-
no-stderr bug D33 already found and fixed in `validate.py`. Rather than duplicate the fix
a second time, extracted `_subprocess_error_detail` into a new shared
`corpus/subprocess_utils.py` (matching `manifest_io.py`'s own "shared between corpus
scripts, neither imports the other" rationale) and pointed both call sites at it —
CLAUDE.md's "never let a metric/logic live in more than one place" applies to error
formatting too, not just scoring.

Corpus is now 5 repos, all 5 with real captured baselines: 1,406 total baseline tests
(`fastapi-plugins` 54, `pydantic-argparse` 746, `rohmu` 195, `iscc-core` 319, `kor` 92) —
up from 2 repos / 411 tests. All 3 newly captured repos also passed the post_sha sanity
check (the human's own migration is green under v2), so they're valid ground truth, not
just "installs and runs."

**Interview:** "Four repos, four different failure reasons, and a generic
`CalledProcessError` message that told me nothing about any of them. Rather than either
lowering the bar to let them through or writing off the four and searching for easier
repos, I reproduced each Docker build by hand outside the harness to get the real stderr.
Three turned out to be genuine curation mistakes I could fix honestly — a missing system
library, a build tool that doesn't understand a project's actual extras naming, a test
suite implicitly assuming infrastructure the sandbox doesn't provide — and one turned out
to be a repo that was never going to work here no matter what I changed, because it isn't
a library at all. Getting that distinction right, repo by repo, mattered more than hitting
a corpus-size number quickly."

---

## D40 — Minimal eval harness (`eval/metrics.py` + `eval/harness.py`), not full Phase 5

**Alternatives:** build the full `EvalConfig`/`RepoResult` ablation harness interfaces.md
§8 originally sketched (retrieval strategy, tiers, seed, resumable parallel Docker runs)
now, since Phase 4's own acceptance criteria need SOME harness to exist; skip building a
harness at all and hand-run repos one at a time to eyeball numbers.

**Why:** phase-4-triage.md's acceptance criteria (classifier accuracy on ≥100 hand-
labelled failures, measured pass-rate lift vs. Phase 3, cost per repo, per-class fix-rate
table) all need a way to run the loop across corpus repos and score the result — nothing
in the codebase did that yet. Building the FULL Phase 5 harness now would mean designing
`EvalConfig`'s retrieval/tier axes against zero real evidence of what those axes should
even look like — the same "don't guess ahead of evidence" reasoning already applied to
`triage/rules.py`. Instead, built exactly the one axis Phase 4 itself needs:

- `eval/metrics.py`: `RepoScore` (pass_rate over `baseline.passed` only per I4, full_green,
  iterations, usd_spent, wallclock_s, final diagnosis class counts) + `score_run()`, a pure
  function — the single place this scoring happens, per CLAUDE.md.
- `eval/harness.py`: `run_repo()` runs one already-checked-out repo through
  `build_migration_graph` and scores it; `run_corpus()` iterates a list of `RepoSpec`s,
  skipping repos without a captured baseline and logging (not crashing on) any repo whose
  clone/build/loop fails, matching `capture_baselines.py`'s own "one bad repo isn't fatal"
  stance. `checkout_pre_sha()` is the one real-git-clone function, deliberately split out
  so `run_repo` itself takes an already-checked-out `source_root` and can be unit-tested
  with `FakeSandbox`/`FakeModelClient` exactly like `tests/agent/test_graph.py` does — no
  network in unit tests (CLAUDE.md).
- `build_migration_graph(..., use_triage: bool = True)`: the ONE ablation axis this pass
  needed. `classify` still runs unconditionally (cheap, and its output is useful raw
  material regardless of arm); `use_triage=False` disables `route()`'s D37 all-PREEXISTING
  skip and `repair()`'s D38 diagnosis-routed target selection, falling back to the
  pre-D37/D38 shape (`collect_failure_texts`, every raw failure in one prompt). This is
  exactly why `collect_failure_texts` was kept in `agent/repair.py` after D38 stopped
  calling it directly — it's the "Phase 3 arm" of this comparison, not dead code.
- `run_repo(..., failures_out=...)` appends every failure still standing at the end of a
  run to a JSONL file: repo_id, node_id, the classifier's predicted class, and the FULL
  raw failure text (via `triage.collect.collect_raw_failures` + `triage.grouping.
  group_raw_failures` — NOT `Diagnosis.evidence`'s ~200-char snippet, which is already
  answer-revealing and useless as blind hand-labelling input). This is the seed data for
  phase-4-triage.md's "≥100 hand-labelled real failures" requirement — the labelling and
  accuracy-scoring step itself is still future work, now unblocked rather than blocked on
  a chicken-and-egg "no data to label" problem.

Deliberately NOT in this pass (unchanged from the original proposal): per-class fix-
success table (needs `AgentState` to retain repair-attempt/run history it doesn't have —
a real design question better answered once a live corpus run's shape is known),
diff-line-Jaccard vs. the human's migration (a Phase 5 ablation-comparison metric, not
something Phase 4's criteria need), and the full `EvalConfig` axes.

Found live while writing `eval/harness.py`'s own tests (see D41): `agent/graph.py`'s
`edit_t1` had a real, previously-unexercised bug — every existing `test_graph.py` test
hand-constructs a non-empty `work_list`, so nothing had ever run `build_migration_graph`
against a repo where `graph/relevance.py`'s signal detection legitimately finds zero
T1-flagged units anywhere (a real, plausible corpus shape, not a contrived edge case).

**Interview:** "Phase 4's acceptance criteria are all measurement criteria — they can't be
satisfied by more triage logic, only by actually running the loop and counting. I built
exactly enough harness to make that measurement possible: one real ablation axis
(triage on/off), pure scoring, and a side-channel dumping real failure text for the
hand-labelling step that has to happen before classifier accuracy means anything. I didn't
build the retrieval/tier ablation machinery Phase 5 will eventually want, because I have
zero evidence yet about what those axes should look like — building them now would be
designing against a guess, the same mistake `triage/rules.py`'s own docstring already
argues against."

---

## D41 — `edit_t1` skipped populating the overlay for a zero-signal repo (real bug, not a test artifact)

**Alternatives:** work around it in the test fixture (give the test source content that
happens to trip a T1 signal) and leave the underlying gap undiscovered; make `repair()`
defensively create missing overlay files on demand instead of fixing `edit_t1`.

**Why:** `eval/harness.py`'s first test using a REAL `graph/relevance.py` work_list
(instead of every existing `test_graph.py` test's hand-constructed `work_list=[[_unit()]]`)
crashed `repair()` with `FileNotFoundError` — `overlay_root` was completely empty.
Root cause: `edit_t1`'s guard `if not remaining_batches: return {}` (where
`remaining_batches = state.work_list[state.cursor:]`) treats "work_list is empty because
there's genuinely nothing for T1 to touch anywhere in the repo" identically to "work_list
is empty because a previous call already finished it" — but only the second case should
skip the function's full-repo file-copy loop. The first case is exactly what a real repo
whose pydantic usage doesn't trip any of `relevance.py`'s signal detectors looks like
(plausible for many real repos, not a contrived fixture), and `edit_t1`'s own docstring
already says the file-copy loop is NOT supposed to be gated on work_list content at all
("it no longer gates which files T1 is allowed to touch") — the guard just didn't
actually implement that for the zero-units case.

Fixed by distinguishing the two cases with `state.cursor > 0` (the loop only skips on a
LATER call once there's provably nothing left, never on the first call): `if not
remaining_batches and state.cursor > 0: return {}`. Rejected the defensive-repair
alternative because it would paper over the actual bug — `repair()` correctly assumes
`overlay_root` mirrors `source_root` for every first-party file; the fix belongs where
that invariant is supposed to be established, not where it's consumed.

Noted but explicitly NOT fixed here (out of scope for this pass, flagged separately):
`edit_t1` always advances `cursor` straight to `len(state.work_list)` in one call (D17's
eager-processing redesign), which means `state.current_batch` is `None` by the time
`route()` ever runs — `route()`'s `"next_unit"` branch (and therefore a second `edit_t1`
call ever happening) appears to be unreachable dead code in the current graph topology.
Worth a real look, but unrelated to this bug and not blocking Phase 4's harness work.

**Interview:** "Every existing test for this loop hand-built its work_list, which meant a
whole real code path — `edit_t1` running with a work_list `relevance.py` actually
produced — had never executed once. The first time it did, in the harness's own test
suite, it crashed immediately. That's the value of testing against a real pipeline instead
of only against hand-picked fixtures: the fixtures were all secretly assuming a
precondition (`work_list` is never empty) that nothing enforced and that a real repo can
violate."

---

## D42 — `eval/harness.py` built the run-time image at the wrong pydantic version

**Alternatives:** discover this only after the full paid corpus run produced nonsense
numbers; add a defensive check somewhere that papers over the symptom (e.g., special-
case "many collection errors" as its own thing) instead of fixing the actual image
version.

**Why:** a smoke test against a single cheap repo (`iscc-core`) before committing to a
real API-spending corpus run showed 19 collection errors and only 2 collected tests,
against a repo `capture_baselines.py` had already measured at 319 passing tests for the
identical repo/sha. Root cause, found by comparing a direct `sandbox.build` +
`run_tests` call (worked, 319/0) against the harness's own `run_repo` path (broken,
2/19): `run_corpus` called `sandbox.build(repo, "v1")` for the image every `run_tests`
call in the loop reuses for the whole run. But T1 runs unconditionally and immediately
(D17/D19) — its very first pass rewrote `iscc_core/options.py` to
`from pydantic_settings import BaseSettings` / `ConfigDict(...)`, real v2-only syntax.
Tested against a pydantic-v1-pinned image with no `pydantic_settings` package installed
at all, every module that imports `options.py` (nearly the whole test suite) failed to
even collect. The agent's actual design has never worked any other way: T1/T2
progressively rewrite *source* from v1 to v2 syntax against one CONSTANT v2-pinned
image for the whole loop — `capture_baselines.py`'s own `sanity_check_post_sha` already
builds at `post_sha` under `"v2"` for exactly this reason, and nothing else in the
codebase ever called `sandbox.build(repo, "v1")` outside `capture_baselines.py`'s
separate, standalone pre_sha-under-v1 baseline-measurement flow — only this harness had
it backwards, because I wrote it that way.

Fixed by building at `"v2"` instead. Re-ran the same smoke test after the fix: `pass_rate
1.0`, `full_green=True`, `usd_spent=0.0` — an exact match for D35's earlier T1-only 100%
result, confirming the harness is now measuring the same thing the rest of the project
already validated by hand.

**Interview:** "This is exactly why I smoke-tested one cheap repo before running the
whole paid corpus: the bug would have silently produced a corpus-wide result showing
near-total collection failure, and without a known-good baseline to compare against I
might have read that as 'the model can't fix these repos' instead of 'the harness is
testing against the wrong environment.' Comparing a working manual sandbox call against
my own harness's path made the actual divergence obvious in under a minute, instead of
debugging from five confusing repo-level failures after spending real API budget on all
of them."

---

## D43 — `sandbox/runner.py` swallowed real stderr on a fatal conftest crash

**Alternatives:** leave the generic placeholder message and treat "no json report" repos
as simply unclassifiable; only fix this inside `eval/harness.py` (e.g. re-run manually
outside the sandbox to get a real error) rather than in `sandbox/runner.py` itself.

**Why:** found live during the first real corpus run — `Aiven-Open__rohmu` and
`SupImDos__pydantic-argparse` both scored `pass_rate=0.0` with `agent.classify
classes=['unknown']`, and the only available diagnostic was `DockerSandbox.run_tests`'s
placeholder: "no json report produced — the container likely crashed, was OOM killed, or
exited before pytest could write output." Reproducing rohmu's container run directly
showed the REAL cause was neither a crash nor OOM: a `@root_validator` raising
`PydanticUserError` at class-definition time in `rohmu/object_storage/config.py`,
imported transitively by `conftest.py` — a completely legible, well-formed pytest error
(exit code 4, "usage error," since a fatal conftest load failure aborts pytest's entire
session before `--continue-on-collection-errors` or the json-report plugin's finish hook
ever get a chance to run). `subprocess.run(args, capture_output=True, ...)`'s return
value was captured into an unused expression — `result.stderr` had the exact error text
in it the whole time; nothing downstream ever read it. Exactly the same class of bug as
D33/D39's swallowed-`CalledProcessError`-stderr fix, in a third module now.

Fixed by reading `result.stdout`/`result.stderr` (last 4000 chars each, decoded) into the
`_crashed_result` message whenever `report_file` doesn't exist, alongside the real exit
code. This is squarely a `sandbox/runner.py` fix, not something to work around one layer
up in `eval/harness.py` — every future caller of `Sandbox.run_tests` (not just this
harness) gets an honest, actionable error instead of a placeholder indistinguishable from
a genuine OOM kill.

**Interview:** "The corpus run's own numbers told me something was wrong — two repos
losing 100% of their tests to 'unknown' is not what a working classifier looks like on
real corpus data. But the fix wasn't in triage at all; the classifier was doing exactly
what it should with the only input it was ever given, a generic placeholder string with
zero signal. The actual bug was one layer down, in a module already-verified against a
live Docker daemon (docs/phase-2-sandbox.md) — verification had covered timeout handling,
network isolation, and cache-hit timing, but never a fatal conftest-load failure
specifically, because nothing in that verification pass had hit one yet."

---

## D44 — `src/`-layout editable installs bypass the sandbox overlay entirely (confirmed, fixed in D46)

**Alternatives:** investigate and fix the entrypoint mechanism now, before trusting any
corpus number (blocks the run); drop `SupImDos__pydantic-argparse` from the corpus
entirely, same call as `plugboard`/`COSCUP` (D32/D39); keep it in the run and explicitly
mark its result unreliable rather than fixing or excluding it right now — **this is the
option chosen**, so the corpus run continues with 5 repos and this one caveat.

**Why:** `SupImDos__pydantic-argparse` scored `pass_rate=0.0` on every arm with
`agent.classify classes=['unknown']` and `repair_no_target`. Confirmed by direct
reproduction (not inference): built the image, ran the container with an overlay whose
`src/pydantic_argparse/__init__.py` was replaced with a single `raise
RuntimeError("OVERLAY_TEST_CANARY_ARGPARSE")` — the test run still failed with the
ORIGINAL unmigrated code's error (`AttributeError: module 'pydantic' has no attribute
'fields'`), never touching the canary at all. The traceback's frames were absolute
(`/repo-base/src/pydantic_argparse/__init__.py:12:`), not `/repo`-relative — confirming
imports resolve through the package's editable-install path mapping (baked in at image
BUILD time, pointing at `/repo-base`), completely bypassing the tmpfs+overlay mechanism
`sandbox/policy.py`'s own docstring describes ("agent edits applied as a writable
overlay... a run can never corrupt the corpus checkout"). Ran the identical canary
against `iscc__iscc-core` (a flat, non-`src/` layout) first as a control — that repo's
overlay DID take effect (the canary crashed every test that imports the package, as
expected) — so this is specifically a `src/`-layout + editable-install interaction, not a
general overlay failure across the whole corpus.

This means: for ANY `src/`-layout corpus repo, the agent's T1/T2 edits are being
evaluated against test results that can never reflect them. `pydantic-argparse`'s
`pass_rate=0.00` in every recorded run (docs/decisions.md D40's corpus run) reflects the
UNMIGRATED baseline tested at pydantic v2, not the agent's actual capability — it is not
honest evidence of anything the agent did or didn't do, and must not be read as such
(interviews, `docs/results/`, or otherwise) until this is fixed. `src/`-layout is a
common, not-rare Python packaging convention — this is worth fixing for real, just not
inside the same session as the eval harness's own build (a Phase 2 sandbox-design fix is
its own scope, likely needs its own interfaces-first proposal per CLAUDE.md, given
`docs/phase-2-sandbox.md` already marked that module's acceptance criteria met once
before).

**Interview:** "The corpus run's own numbers were the tell again — a `pass_rate` of
exactly 0.00 with zero variation across both ablation arms, on a repo whose real baseline
had 746 tests, doesn't look like 'the agent failed,' it looks like 'nothing was ever
actually tested.' I didn't guess at the mechanism — I proved it with a canary edit and a
control repo, the same evidence-first standard this project holds triage's own regex
rules to. I chose not to fix the actual sandbox bug in the same pass as the eval harness
work: it's a real, separate, load-bearing piece of Phase 2 that deserves its own
interfaces-first look, not a rushed patch bolted onto an unrelated deliverable."

---

## D45 — `run_corpus` didn't clean `overlay_root` between runs, silently understating T1

**Alternatives:** always use a fresh `tempfile.TemporaryDirectory()` per repo per call
instead of a caller-supplied `work_root` (loses the ability to inspect a run's overlay
content afterward for debugging, which is exactly what made D42/D44 possible to diagnose
in the first place); leave it and just remember to manually clean `work_root` before
every re-run (relies on remembering, the same class of mistake this fix removes).

**Why:** found live, immediately after fixing D43 — a re-run of the full corpus against
the SAME `work_root` (needed to verify D43's fix) showed `edits_applied=0` for repos that
had shown real, nonzero T1 edits in the previous run. Root cause: `run_corpus` did
`overlay_root.mkdir(parents=True, exist_ok=True)` — creates the directory if missing, but
leaves existing content untouched if it already exists. `edit_t1` only writes a file into
`overlay_root` when it's NOT already there (`if not dst_file.exists(): dst_file.write_text(...)`,
by design — the loop that populates the overlay is meant to run once per fresh checkout,
not to re-copy over edits already made this same run). On a SECOND run against the same
`work_root`, every file already existed in `overlay_root` from the FIRST run — already
carrying that run's T1 rewrites — so `apply_rules(before, path, ALL_RULES)` correctly saw
`before == after` (nothing left to change) and reported zero new edits, silently and
plausibly, with no error or warning anywhere. This is the exact "produces a number that
isn't honest" failure mode CLAUDE.md's review checklist calls out, just one level removed
from the number itself (an internal bookkeeping count, not the final score) — caught only
because the SAME repo's `edits_applied` visibly changed between two runs that should have
been identical, not because anything crashed.

Also relevant given D45 sits right next to `checkout_pre_sha`'s own D-numbered
idempotency fix earlier this session (cleaning `source_root` before `git clone`): the two
bugs are the same root mistake — `mkdir(exist_ok=True)`-style "create if missing" logic
applied to a directory whose CONTENT, not just existence, needs to be fresh per run — made
independently in two different functions because I fixed the clone-failure symptom first
without checking whether the overlay had the identical class of problem.

Fixed by unconditionally `shutil.rmtree`-ing `overlay_root` before recreating it, mirroring
`checkout_pre_sha`'s pattern for `source_root`.

**Interview:** "This is the harness lying to itself, not to me — the corpus run's actual
SCORES weren't wrong (each iteration's test outcomes were still real), but the T1
edit-count telemetry silently went stale between runs, and nothing about the code would
have told me that without noticing the number itself looked different from before. The
lesson I'm taking from finding this right next to the checkout fix: when you find one
'stale state from a previous run' bug, check every OTHER piece of state the same function
touches for the identical assumption, instead of declaring victory on the first one."

---

## D46 — Fixed D44: rewrite editable-install paths at build time, not the entrypoint

**Alternatives:** re-run `pip install -e .` against `/repo` in the entrypoint, after the
overlay copy, so the editable-install metadata gets regenerated pointing at the tmpfs copy
instead of `/repo-base`; parse and patch only the specific `.pth`-file shape confirmed in
D44, leaving the (unobserved in this corpus, but real) PEP 660 `__editable__*_finder.py`
shape unhandled.

**Why:** confirmed the exact mechanism first, not just the symptom — built
`SupImDos__pydantic-argparse`'s image and inspected site-packages directly inside the
running container. `pip install -e .[test]` (run at `WORKDIR /repo-base`) has setuptools
pick its "compat" editable strategy for this repo: a single `.pth` file
(`_editable_impl_pydantic_argparse.pth`) containing the literal line `/repo-base/src`. Every
`.pth` file in site-packages gets appended to `sys.path` by Python's own `site` module at
interpreter startup, and that absolute path was captured once, at image-BUILD time — baked
into the read-only image layer, never revisited. `/repo-base` still physically exists
(read-only) at container runtime right alongside the writable `/repo` tmpfs, so every import
resolves against the stale reference copy no matter what the entrypoint copies into `/repo`
afterward. No PEP 660 finder module exists for this repo (confirmed absent) — just the
plainer `.pth` shape.

Rejected re-running the editable install in the entrypoint: the entrypoint runs as non-root
(`policy.py`'s `NOBODY_UID_GID`) against a `--read-only` container root, and site-packages
lives on that read-only filesystem, not the `/repo` tmpfs — there's nowhere writable to
reinstall into without adding a second tmpfs and a write path into Python's install
location, undercutting the exact read-only-root security model D13/D14 already built. It
would also turn a one-time build cost into a per-container-run step invoking the package's
build backend on every single test run — a real regression against `image.py`'s own
documented 0.03s cache-hit overhead, and a fresh source of run-to-run variance that PLAN.md's
I6 exists to rule out.

Fixed by adding one build-time-only step (root, writable filesystem — the same phase D14's
`cp -r` fix and D27's platform pin already operate in) to `DOCKERFILE_TEMPLATE`: a new
script, `FIX_EDITABLE_PATHS_SCRIPT` (`image.py`), run once via `RUN python3
/fix_editable_paths.py` right after the pydantic-pin step, that walks every site-packages
directory this image's Python(s) actually use (`site.getsitepackages()`, plus
`/repo-base/.venv/lib/python*/site-packages` for `uv`-based repos — same detection
convention D27 already established) and rewrites the literal byte string `/repo-base` to
`/repo` in every text file that contains it (skipping any file containing a NUL byte, so a
compiled `.so` that happens to contain that byte sequence can never be corrupted by a
length-changing replace). Chose a textual rewrite over parsing-and-patching the `.pth`
format specifically because it covers the PEP 660 finder-module shape too — the finder just
embeds the same absolute path as Python string literals in a generated `.py` file — with the
same one mechanism, rather than one fix per editable-install strategy. `compute_deps_hash`
already hashes `dockerfile_template` wholesale (D14's own lesson), so this automatically
busts the cache; the new script's content was added to the hash payload explicitly too, for
the same reason.

Verified with the identical canary technique that found the bug, not just by reading the
diff: rebuilt `pydantic-argparse`'s image (new tag, confirming the cache-bust worked),
re-ran the same `raise RuntimeError("OVERLAY_TEST_CANARY_ARGPARSE_POSTFIX")` overlay edit to
`src/pydantic_argparse/__init__.py` through the real `DockerSandbox.run_tests` — the run now
fails immediately with that RuntimeError, traceback rooted at `/repo/...`, proving the
overlay is actually reaching the test. Re-ran the `iscc__iscc-core` (flat-layout) control
the same way to confirm it's unaffected — still crashes on its own canary exactly as before.
Full `pytest -q` (287 passed, 2 pre-existing failures in `tests/eval/test_metrics.py`
unrelated to this change — `score_run`'s `pass_rate` calculation, no `sandbox` import
anywhere in `metrics.py` — flagged separately, not fixed here) and `mypy --strict
src/pmigrate` (clean) both pass.

**Interview:** "I didn't guess at the fix any more than D44 guessed at the bug — I built the
actual image and read the `.pth` file setuptools wrote, which showed it's just one literal
absolute path baked in at install time. That ruled out my first instinct, re-running the
install at container-start, the moment I checked where that would have to write: site-
packages sits on the sandbox's read-only root, not the writable tmpfs, so there's no legal
place to redo an editable install after the container starts without weakening the security
model D13 already earned. The actual fix is a one-time, build-time textual rewrite, and I
trust it because I reran the exact canary that found the bug and watched it fail for the
right reason instead of the wrong one, plus the flat-layout control to make sure I hadn't
broken the case that already worked."

---

## D47 — `cumulative_outcomes`: `score_run` was undercounting pass_rate on multi-iteration runs

**Alternatives:** merge outcomes directly into `last_run` instead of a separate field
(rejected: `route()`, `classify_node`, and `NoProgressDetector` all deliberately want the
NARROW per-iteration view — merging would risk changing three already-tested, working
control-flow paths to fix a problem that only exists in scoring); track only a
`frozenset[str]` of "ever seen passing" instead of a full `dict[str, TestOutcome]`
(rejected: "once passed, always passed" can't represent a later regression on a node_id
that DOES get re-selected and re-tested — a dict keyed by node_id, most-recent-write-wins,
handles both the common case and that edge case with the same structure).

**Why:** found live on the exact corpus run this decision documents. `run_tests_node`'s
`selection` optimization (protocol.py: "selection lets triage re-run just the failures")
means every test run after the first only re-tests previously-failing node_ids — a real,
intentional performance optimization, not a bug. But `eval/metrics.py`'s `score_run`
(D40) computed `pass_rate` from `final_state["last_run"].outcomes` alone, which is exactly
that narrow, selection-limited set once any repair has happened. Watched it happen live:
`Aiven-Open__rohmu` genuinely reached 173/195 passing after a real repair (iteration 2,
a full-suite run), then iteration 3 re-tested only the 22 still-failing node_ids
(`passed=1, total=22`) — and a repo finishing on an iteration like that would score as
~1/195 instead of the true ~174/195. Confirmed even more starkly on `iscc__iscc-core`
under the `use_triage=False` arm: a real corpus run reported `pass_rate=0.00` for a repo
independently known (D35) to sit at 315/319 passing before any repair even runs — the
narrow final iteration's 4-outcome selection completely erased the other 315.

Fixed with a new, purely additive `AgentState.cumulative_outcomes: dict[str, TestOutcome]`
field, updated by `run_tests_node` on every call (`{**old, **{o.node_id: o for o in
run.outcomes}}` — new observations overwrite old ones for the same node_id, everything
else carries forward untouched). `score_run` now reads this instead of `last_run.outcomes`
for `pass_rate`; every other consumer of `state.last_run` (`route()`, `classify_node`,
`NoProgressDetector`) is completely untouched, so this fix cannot change any control-flow
decision the loop already makes — only what gets reported about the final result. Verified
with a new direct test (`test_cumulative_outcomes_carries_forward_a_test_not_covered_by_a_
later_narrow_run`, `tests/agent/test_graph.py`) that scripts a `FakeSandbox`'s second
response to contain ONLY the previously-failing node_id, matching a real selection-narrowed
run, and asserts the untouched node_id is still reported correctly.

**Interview:** "I found this one the way the project has found every real bug this
session — a number that looked wrong on real data, not a code review catch. `iscc-core`
scoring 0% under a config where I *knew* from an earlier, independently-verified run
(D35) that it sits at 99% before the agent even does anything, was the tell. The fix
itself is deliberately narrow: one new field, one write site, one read site, and a
one-sentence argument for why it can't touch the three places that already work
correctly on the narrow view they were designed around."

---

## D48 — Added GroqModelClient: Gemini's free tier can't support real development

**Alternatives:** wait out Gemini's free-tier quota (rejected — see below); enable
billing on the Gemini key instead of adding a second provider; get a real Anthropic or
OpenAI key.

**Why:** Gemini's `gemini-3.6-flash` free tier (`GenerateRequestsPerDayPerProjectPerModel-
FreeTier`, limit 20) turned out not to be a clean once-a-day reset. Direct evidence: fully
exhausted by ~11pm, still 429ing after 35+ minutes of retries, then ONE call succeeded at
09:40 the next morning — and the very next call, seconds later, 429'd again with a ~33s
retry hint. That's a slow trickle-refill (something on the order of one request/hour), not
a daily bucket — unusable for iterative development, where a single debugging cycle
(change code, retest) needs a fast turnaround, and unusable at any real scale for Phase 5's
larger ablation matrix.

Considered enabling Gemini billing instead of adding a new client — genuinely the cheapest
option in isolation (Gemini's own pay-as-you-go pricing is lower per-token than Groq's for
comparable models). Went with Groq anyway because a real key was already in hand and
verified working end-to-end in minutes, at zero cost, with headroom that makes the billing
question moot for this project's actual call volume: `openai/gpt-oss-120b` on this account
measured `x-ratelimit-limit-requests: 1000` (confirmed against Groq's own published
developer-plan docs at console.groq.com/docs/models: 1K RPM, 250K TPM) — orders of
magnitude beyond what a handful of corpus runs need. Real, verified pricing sourced from
that same page ($0.15/1M input, $0.60/1M output) rather than guessed, matching
`GeminiModelClient`'s own no-silent-$0 stance — `_GROQ_PRICE_PER_TOKEN_USD` raises
`ValueError` for any model without a confirmed entry, same as Gemini's dict.

`GroqModelClient` mirrors `GeminiModelClient`'s shape exactly (same `ModelClient` Protocol,
same `from_env()` pattern, same temperature=0 for I6 reproducibility) against Groq's
OpenAI-compatible `/chat/completions` endpoint. The empty-response guard
(`GeminiEmptyResponseError` → renamed `ModelEmptyResponseError`) is now shared across both
providers rather than named after whichever one happened to hit the failure mode first —
a small, real rename since it stopped being Gemini-specific the moment a second real
client needed the identical guard for the identical reason (a `max_tokens` budget consumed
entirely by internal reasoning before any visible output).

Gemini's client and key are kept, not removed — real comparison data, and useful if
Groq's own limits ever become the constraint instead.

**Interview:** "The free tier's failure mode here wasn't obvious from the error message
alone — 'quota exceeded, limit 20' reads exactly like a clean daily reset until you watch
it not reset after 35 minutes, then partially recover by exactly one request the next
morning. I didn't guess at Groq's pricing either, even though I generally know their
public numbers are cheap — I pulled the actual current developer-plan table and cross-
checked it against the account's own rate-limit headers before writing a number into code
that this project's own cost-reporting depends on. Reusing GeminiModelClient's exact shape
for the new client, down to the same reproducibility argument for temperature=0, was
deliberate: this seam is supposed to make a provider swap a non-event everywhere else in
the codebase, and it was — zero changes needed in agent/graph.py."

---

## D49 — `GroqModelClient` retries a transient 429 instead of failing the whole repo run

**Alternatives:** handle the retry in `agent/graph.py`'s `repair()` instead of inside
the client; don't special-case 429 at all and rely on `agent/graph.py`'s existing
`repair_failed` → `status="failed"` path (D24) to just end the run, same as Gemini's.

**Why:** the very first live corpus run against `GroqModelClient` (right after D48)
showed a real, different failure shape than Gemini's: Groq's 429 recovers within seconds,
not hours — several repos hit exactly one transient rate-limit and then `repair()`'s
D24-era handling (any `complete()` exception → `status="failed"`, run ends) stopped them
cold. `Aiven-Open__rohmu` is the clearest evidence: a run ended after one 429 with zero
progress, on a repo independently known (an earlier Gemini run, same session) to go from
fully blocked to 173/195 passing in exactly two successful calls. The rate-limit itself
wasn't the problem — giving up immediately after hitting it was.

Rejected handling this in `repair()`: that function's exception handling is deliberately
generic (any `ModelClient`, any provider) and correctly treats every OTHER failure —
malformed response, auth error, `ModelEmptyResponseError` — as genuinely fatal. Whether a
429 is "wait a few seconds and it'll work" or "this key is done for the day" is provider-
specific knowledge (Gemini's isn't, Groq's is) that belongs inside the client actually
talking to that provider, not leaked into the shared loop. `GeminiModelClient` gets no
equivalent retry — its 429 was a structural daily-quota wall (D48); retrying there would
only waste wall-clock time reproducing the same failure.

`GroqModelClient._post_with_retry` retries up to 3 times, respecting the server's own
`Retry-After` header when present (a real HTTP convention, not a Groq-specific guess) and
falling back to a short fixed delay (2s, 4s, 6s) otherwise. From `repair()`'s perspective
a retried-then-succeeded call is indistinguishable from an immediately-successful one —
the seam this client sits behind still returns exactly one `ModelResponse` or raises,
same as before.

**Interview:** "The first real corpus run against the new client told me the failure
mode wasn't the same as Gemini's, even though the HTTP status code was identical — 429
means completely different things depending on the provider's actual quota model, and
conflating them would have meant either wastefully retrying Gemini's daily wall or
giving up too early on Groq's momentary one. I already had the evidence for both, from
two runs in the same session against the same repos, so this wasn't a guess about which
behavior each provider needed."

---

## Template

```
## D<n> — <decision>
**Alternatives:**
**Why:**
**Interview:**
```
