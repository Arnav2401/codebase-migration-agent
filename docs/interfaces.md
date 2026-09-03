# Cross-module contracts

These are the seams. Get them right and phases can be built and swapped independently;
get them wrong and everything couples. Types are illustrative — refine as you implement,
but **change them here first**, then in code.

All shared types live in `src/pmigrate/types.py`. Nothing below imports from a sibling
component's internals; components talk only through these.

---

## 1. Corpus (Phase 0)

```python
@dataclass(frozen=True)
class RepoSpec:
    repo_id: str                 # "pydantic-org__example" — filesystem/image safe
    url: str                     # https://github.com/org/name
    pre_sha: str                 # parent of the human migration commit
    post_sha: str                # the human migration commit
    python_version: str          # "3.11"
    install_cmd: list[str]       # ["pip", "install", "-e", ".[test]"]
    test_cmd: list[str]          # ["pytest", "-q"]
    setup_overrides: list[str]   # extra shell lines injected into the Dockerfile
    split: Literal["dev", "test"]
    baseline: BaselineResult     # captured at pre_sha with pydantic v1
    human_diff_stats: DiffStats  # files/lines/symbols changed by the human

@dataclass(frozen=True)
class BaselineResult:
    passed: frozenset[str]       # test node ids that pass pre-migration  <-- invariant I4
    failed: frozenset[str]       # pre-existing failures, excluded from scoring
    skipped: frozenset[str]
    duration_s: float
```

`corpus/manifest.json` is a list of `RepoSpec`. It is **hand-curated and committed**.
Discovery scripts propose entries; a human accepts them.

---

## 2. Graph (Phase 1)

The store is behind a protocol so the Neo4j backend can be swapped for an in-memory one.

```python
class SymbolKind(StrEnum):
    MODULE = "module"; CLASS = "class"; FUNCTION = "function"; METHOD = "method"; ASSIGNMENT = "assignment"

@dataclass(frozen=True)
class SymbolRef:
    repo_id: str
    fqname: str                  # "app.models.User.validate_email"
    kind: SymbolKind
    path: str                    # repo-relative
    start_line: int; end_line: int

class EdgeKind(StrEnum):
    CONTAINS = "CONTAINS"        # module -> class -> method
    IMPORTS = "IMPORTS"          # module -> module
    REFERENCES = "REFERENCES"    # symbol -> symbol (name used)
    CALLS = "CALLS"              # symbol -> callable
    INHERITS = "INHERITS"        # class -> base class
    DECORATES = "DECORATES"      # decorator -> decorated symbol

class CodeGraph(Protocol):
    def ingest(self, repo: RepoSpec, root: Path) -> IngestStats: ...
    def get(self, repo_id: str, fqname: str) -> SymbolRef | None: ...
    def dependents(self, ref: SymbolRef, *, depth: int = 1,
                   kinds: set[EdgeKind] | None = None) -> list[SymbolRef]:
        """Who would break if this changed. Incoming REFERENCES/CALLS/IMPORTS/INHERITS."""
    def dependencies(self, ref: SymbolRef, *, depth: int = 1,
                     kinds: set[EdgeKind] | None = None) -> list[SymbolRef]:
        """What this needs. Outgoing edges."""
    def topo_modules(self, repo_id: str) -> list[list[str]]:
        """Modules in migration order, leaves first. Inner lists are SCCs
        (Python has circular imports); members of an SCC must be migrated together."""
    def neighbourhood(self, ref: SymbolRef, budget_tokens: int) -> list[SymbolRef]:
        """Context selection for a prompt: BFS out from ref, ranked, truncated to budget.
        This is the function the retrieval ablation swaps out."""
```

`relevance.py` sits on top and answers the question that actually drives the agent:

```python
@dataclass(frozen=True)
class MigrationUnit:
    module: str                  # "app.models"
    path: str
    symbols: list[SymbolRef]     # pydantic-touching symbols in this module
    signals: set[str]            # {"BaseModel", "validator", "Config", "dict_call", ...}
    est_difficulty: int          # 0-3 heuristic from signals

def work_list(graph: CodeGraph, repo_id: str) -> list[list[MigrationUnit]]:
    """Topologically ordered batches of units that touch pydantic. THIS IS THE PLAN."""
```

> The retrieval layer produces the *task list*, not just context. That's the point.

**Implementation update (Phase 1 build):** the signature above assumed a `CodeGraph` alone
carries enough information to answer "does this symbol need migrating." In practice signal
detection needs decorator names, call sites, and `Field()` kwargs — the parsed IR — which a
`CodeGraph` has no reason to retain once it's built the node/edge structure (retaining it
would mean bloating every Symbol node with parser-specific properties, or re-parsing at
query time and losing "ingest once, query many times"). The actual implementation is
`relevance.compute_work_list(resolved: ResolvedRepo, repo_id: str) -> list[list[MigrationUnit]]`,
operating directly on resolver.py's output instead of a `CodeGraph`. Worth deciding for real
once Phase 3 wires up the planner: either `CodeGraph` grows a `signals(ref) -> frozenset[str]`
query backed by properties computed at ingest time, or the planner keeps the `ResolvedRepo`
around alongside the graph. Not resolved — flagged here rather than silently diverged.

---

## 3. Sandbox (Phase 2)

```python
@dataclass(frozen=True)
class SandboxPolicy:
    network: Literal["none", "build-only"] = "build-only"
    memory_mb: int = 4096
    cpus: float = 2.0
    pids_limit: int = 512
    timeout_s: int = 900
    read_only_root: bool = True
    tmpfs: tuple[str, ...] = ("/tmp",)

@dataclass(frozen=True)
class TestOutcome:
    node_id: str                 # "tests/test_models.py::test_user"
    status: Literal["passed", "failed", "error", "skipped", "xfailed"]
    duration_s: float
    message: str | None          # short repr
    traceback: str | None        # trimmed
    captured_stdout: str | None

@dataclass(frozen=True)
class TestRun:
    outcomes: list[TestOutcome]
    collection_errors: list[str] # import-time explosions — the single most common v2 failure
    exit_code: int
    duration_s: float
    truncated: bool

class Sandbox(Protocol):
    def build(self, repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> ImageRef:
        """Cached by (repo_id, sha, deps-hash, pydantic). Network allowed here only."""
    def run_tests(self, image: ImageRef, workdir_overlay: Path,
                  policy: SandboxPolicy, selection: list[str] | None = None) -> TestRun:
        """Network is OFF. selection lets triage re-run just the failures."""
```

Key detail: `run_tests` mounts the repo read-only and applies the agent's edits as a
writable overlay, so a run can never corrupt the corpus checkout.

**Implementation update (Phase 2 build):** `ImageRef` was referenced but never typed above.
Decided shape:

```python
@dataclass(frozen=True)
class ImageRef:
    tag: str
    repo_id: str
    sha: str
    pydantic: Literal["v1", "v2"]
    deps_hash: str
    test_cmd: tuple[str, ...]   # travels with the image since run_tests() takes no RepoSpec
```

Also, `workdir_overlay` is `Path | None` in the real signature, not `Path` — a run with no
edits yet (the first full-suite baseline check before the agent has touched anything) has
nothing to overlay.

**A real finding worth keeping, not just a note:** verified locally (no Docker needed —
this is about pytest's own behavior) that without `--continue-on-collection-errors`, a
single broken import in ONE file aborts pytest's *entire session* — `report["tests"]`
comes back completely empty even for files with nothing wrong. Naive code reading that as
"0 failures, so it passed" would silently report every migration that breaks an import as
a clean success. `runner.py` passes the flag unconditionally; see docs/decisions.md D12.

---

## 4. Codemod (Phase 3, tier T1)

```python
class CodemodRule(Protocol):
    id: str                      # "validator_to_field_validator"
    description: str
    confidence: Literal["mechanical", "likely", "needs-review"]
    def applies(self, tree: cst.Module) -> bool: ...
    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]: ...

@dataclass(frozen=True)
class RuleEdit:
    rule_id: str; path: str; line: int; before: str; after: str
    note: str | None             # surfaced in the PR body
```

Every rule is a separate file with its own test fixture pair (`before.py` / `after.py`).
`confidence` flows through to the PR confidence score and decides whether T2 re-reviews it.

---

## 5. Agent (Phase 3)

```python
@dataclass
class AgentState:                # the LangGraph state object — mutable, checkpointed
    repo: RepoSpec
    work_list: list[list[MigrationUnit]]
    cursor: int                  # index into work_list
    edits: list[Edit]            # everything applied so far
    last_run: TestRun | None
    diagnoses: list[Diagnosis]   # from triage
    iteration: int
    budget: BudgetState
    trace_id: str
```

Tools exposed to the model — deliberately small, and all read paths go through the graph:

```python
read_file(path, start=None, end=None) -> str
search_symbol(name) -> list[SymbolRef]
get_dependents(fqname) -> list[SymbolRef]
get_dependencies(fqname) -> list[SymbolRef]
apply_patch(unified_diff) -> PatchResult   # validates: applies cleanly, file parses, I1-I3
run_tests(selection=None) -> TestRun       # expensive; rate-limited by budget
```

`apply_patch` is the chokepoint where invariants I1–I3 are enforced. Nothing else writes.

```python
@dataclass(frozen=True)
class BudgetState:
    usd_spent: float; usd_cap: float
    tokens_in: int; tokens_out: int
    iterations: int; max_iterations: int
    started_at: float; wallclock_cap_s: int
    def exceeded(self) -> str | None: ...   # returns the breached limit's name
```

**Implementation update (Phase 3 build):** `AgentState` is real (`agent/state.py`), `status:
Literal["running","done","budget_exceeded","no_progress","failed"]` was added — the graph
needs somewhere to record *why* a run stopped, not just that it did. `BudgetState` is real
and immutable as sketched (`spend()`/`next_iteration()` return new instances; LangGraph node
functions return partial-update dicts it merges in, verified interactively before wiring
the graph — they must not mutate state in place).

The standalone tool-function list above (`read_file`, `search_symbol`, etc., meant to be
exposed to the model) was NOT built this way. What's built instead: `apply_patch` exists
exactly as specified (`agent/patch.py`) and is the enforced chokepoint. The graph→CodeGraph
read tools (`search_symbol`/`get_dependents`/`get_dependencies`) are still deferred — no T2
prompt actually retrieves graph context yet, so there's nothing to call them from. What IS
built and tested end-to-end: the **T1-only path** — `agent/graph.py`'s LangGraph state
machine runs codemods, applies patches, runs tests, and routes on budget/no-progress/
completion with zero LLM involvement, exactly matching docs/phase-3-loop.md's "T1-only is
runnable as a config" acceptance criterion.

`repair()` — the T2/T3 node that calls the model on a failing test run — is real, exercised
against a live model, and now actually applies what it produces (docs/decisions.md
D24/D25/D28), not just `FakeModelClient`. There is still no `ANTHROPIC_API_KEY` in this
environment; two real `ModelClient` implementations exist instead (`agent/model_client.py`):
`GeminiModelClient` against Google's Generative Language API, and `GroqModelClient`
(D48, the primary one in practice — Gemini's free tier turned out to trickle-refill rather
than reset daily, impractical for real iteration) against Groq's OpenAI-compatible endpoint.
Both verified live (a real completion call, real token/cost accounting, sourced pricing)
and share one `ModelEmptyResponseError` for the same "max_tokens consumed entirely by
reasoning" failure mode. Full path, via
`agent/repair.py`: identify a target file from the failure (two strategies — traceback path
parsing, or grepping the repo for a class named in a pydantic `ValidationError` message, D25
explains why one heuristic doesn't cover both real failure shapes) → find any LOCAL base
classes that target file's own classes inherit from but don't define themselves (D28 — a
name-based LibCST heuristic, not full import resolution) → build a prompt with every
resulting file's content and the failure text → ask the model which file(s) actually need
changes and for each one's corrected full content (not a diff — D25 on why) → compute each
diff via the existing `make_unified_diff` → apply each through the same `apply_patch`
chokepoint T1 already uses. A real failure anywhere in that chain (no identifiable target,
no usable response, a model-client exception, a model-named path never shown as context) is
handled explicitly rather than silently producing a bad edit — see D24/D25/D28. Not yet
built: real graph-retrieved context (`search_symbol`/`get_dependents` — D28 explains why a
narrower name-based heuristic covers what's needed so far without it).

One more real-run correction (docs/decisions.md D19): `edit_t1` does NOT scope its codemods
to files named in `work_list`. It runs `ALL_RULES` over every first-party `.py` file under
`source_root` (via `graph/repo_files.read_py_files`) and uses `work_list` only for ordering
and the `unit_module` label attached to each `Edit`. `work_list` comes from `relevance.py`,
whose signal detection targets symbol-level T2 planning (class inheritance, `.dict()`-shaped
calls, nested `Config`) — it has no reason to also detect every AST shape that can reference
`pydantic.BaseSettings` (e.g. a bare parameter type annotation, the real case that surfaced
this), so a file can need a T1 fix without ever appearing in `work_list`. Since T1 rules are
cheap, deterministic, and gated by the same `run_tests` call regardless, scoping them to the
narrower planning set bought nothing and silently dropped real fixes.

---

## 6. Triage (Phase 4)

```python
class FailureClass(StrEnum):
    IMPORT_ERROR        = "import_error"          # pydantic.X moved/removed
    CLASS_DEF_ERROR     = "class_def_error"       # PydanticUserError at import time
    REMOVED_API         = "removed_api"           # .dict/.json/parse_obj/__fields__
    VALIDATION_BEHAVIOUR= "validation_behaviour"  # coercion/strictness changed
    SERIALIZATION_DIFF  = "serialization_diff"    # output shape/format changed
    ERROR_MESSAGE_DIFF  = "error_message_diff"    # test asserts on v1 error text
    THIRD_PARTY_PIN     = "third_party_pin"       # fastapi/sqlmodel needs a version bump
    PREEXISTING         = "preexisting"           # failed on baseline too — ignore (I4)
    FLAKY               = "flaky"                 # passed on rerun
    UNKNOWN             = "unknown"

@dataclass(frozen=True)
class Diagnosis:
    node_ids: list[str]          # failures grouped by shared root cause
    cls: FailureClass
    confidence: float
    evidence: str                # the specific log lines that decided it
    suspect_symbols: list[SymbolRef]   # from traceback frames -> graph lookup
    strategy: str                # strategy id to route to

class Classifier(Protocol):
    def classify(self, run: TestRun, baseline: BaselineResult) -> list[Diagnosis]: ...
```

Classification is rule-first (regex + traceback parsing), LLM only for `UNKNOWN`.
Rules are cheap, deterministic, and testable; that's the whole argument for triage.

Each strategy declares what it is allowed to touch:

```python
@dataclass(frozen=True)
class Strategy:
    id: str
    prompt_template: str         # path under agent/prompts/
    allowed_paths: PathPolicy    # e.g. THIRD_PARTY_PIN may only edit dependency files
    retrieval: RetrievalSpec     # what graph query to run for context
    max_attempts: int
```

**Implementation update (Phase 4 build, docs/decisions.md D36):** `FailureClass` and
`Diagnosis` are real, in `types.py` (as `tuple[...]` fields, not bare `list[...]` — matching
this project's "frozen where possible" convention). `Classifier` lives in
`triage/protocol.py`, matching how `Sandbox`/`CodemodRule` are each kept in their own
module's `protocol.py`. `RuleBasedClassifier` (`triage/classifier.py`) is the real, tested
implementation: `triage/rules.py` classifies by regex against real corpus evidence only
(`IMPORT_ERROR`, `THIRD_PARTY_PIN`, `VALIDATION_BEHAVIOUR`, `CLASS_DEF_ERROR`,
`REMOVED_API`); `triage/grouping.py` checks `PREEXISTING` against `baseline.failed` first
(text-independent — a node that failed before migration is ignored regardless of what its
current failure text says), then groups the rest by (class, root traceback frame) into one
`Diagnosis` per real root cause. `SERIALIZATION_DIFF`, `ERROR_MESSAGE_DIFF`, `FLAKY`, and
the LLM fallback for `UNKNOWN` are NOT built — no real evidence exists yet to design or
verify them against (`FLAKY` also doesn't fit this Protocol's shape at all: it needs two
`TestRun`s to compare, not one). `suspect_symbols` is always `()` — no `CodeGraph` wiring
yet, the same call D25/D28 already made for T2. Wired into `agent/graph.py` (D37): a
`classify` node runs `RuleBasedClassifier` between `run_tests` and `route()`, populating
`AgentState.diagnoses` for real. `route()` uses it for one thing — if every diagnosis is
`PREEXISTING`, finalize/advance without ever calling `repair()`, verified live to actually
skip a real, would-have-cost-money T2 attempt.

**Implementation update (docs/decisions.md D38):** `repair()`'s target-selection now
routes through triage instead of the raw `TestRun`. `triage/grouping.py` exposes
`group_raw_failures(...) -> list[GroupedDiagnosis]` (a new type, NOT a field added to
`Diagnosis`: `Diagnosis.evidence` is a short ~200-char display/grouping snippet, nowhere
near enough for `extract_target_file` to find a `path.py:lineno:` frame in, so
`GroupedDiagnosis` pairs each `Diagnosis` with the full `RawFailure`s it was built from;
`classify_and_group` — the function `Classifier.classify()` actually calls — is now a
thin wrapper: `[g.diagnosis for g in group_raw_failures(...)]`, so the Protocol's
documented `list[Diagnosis]` return shape is untouched). `repair()` groups the current
iteration's raw failures, filters out `PREEXISTING`/`THIRD_PARTY_PIN`/`FLAKY` (nothing a
source rewrite can fix for any of the three — I4, D26, and FLAKY's by-definition
nondeterminism respectively), and picks ONE `GroupedDiagnosis` via a fixed priority order
(`agent/graph.py`'s `_REPAIR_PRIORITY`: mechanical/high-confidence classes like
`IMPORT_ERROR` before `VALIDATION_BEHAVIOUR`, which needs real semantic judgment) rather
than flattening every failure into one prompt regardless of cause. Only that diagnosis's
own failure text reaches the model. Repair logging (`agent.repair_applied` etc.) now
carries `cls`/`strategy` — the raw material for phase-4-triage.md's "per-class fix-success
table" acceptance criterion, not built yet since no repair run has accumulated enough
volume to make one meaningful.

The `Strategy`/`PathPolicy`/`RetrievalSpec` sketch above is NOT built — `repair()`'s actual
allowed-edit-surface enforcement is still `apply_patch`'s I1-I3 chokepoint (unconditional,
not per-strategy), and retrieval is still `agent/repair.py`'s name-based heuristics
(D25/D28), not a graph query. Building real per-strategy policies is follow-on work once
`Classifier` output actually drives `repair()`'s behavior beyond the one routing check above.

---

## 7. Trace (Phase 6)

```python
@dataclass(frozen=True)
class TraceEvent:
    run_id: str; span_id: str; parent_span: str | None
    ts: float
    kind: Literal["phase","llm_call","tool_call","patch","test_run","triage","error"]
    payload: dict                # JSON-serializable, no secrets
    tokens_in: int | None; tokens_out: int | None; usd: float | None
```

JSONL per run + a SQLite index for the dashboard. A run must be fully reconstructible
from its events (invariant I6).

---

## 8. Eval (Phase 5)

```python
@dataclass(frozen=True)
class EvalConfig:
    name: str                    # "graph_retrieval" / "embedding_retrieval" / "t1_only"
    model: str
    retrieval: Literal["graph", "embedding", "wholefile"]
    tiers: set[Literal["T1","T2","T3"]]
    triage: bool
    seed: int
    usd_cap_per_repo: float

@dataclass(frozen=True)
class RepoResult:
    repo_id: str; config: str
    pass_rate: float             # over baseline-passing tests only (I4)
    full_green: bool
    iterations: int; usd: float; wallclock_s: float
    diff_line_jaccard: float
    symbol_precision: float; symbol_recall: float
    failure_classes: Counter
    trace_path: str
```

The harness is resumable (skip completed `(repo, config)` cells), parallel over Docker,
and writes `docs/results/<config>.md` plus a combined `main.md`.

**Implementation update (docs/decisions.md D40, superseded by D57):** D40 pulled a minimal
slice forward into Phase 4 (`RepoScore`, a strict subset of `RepoResult` with a bare
`use_triage: bool` instead of `EvalConfig`), because phase-4-triage.md's own acceptance
criteria couldn't be satisfied without SOME way to run the loop across corpus repos and
score it. D57 (Phase 5's first real step) closed most of that gap: `eval/config.py` now
has the real `EvalConfig` above — full field set, but `retrieval != "graph"` or
`tiers != {T1,T2,T3}` raise `NotImplementedError` rather than silently running the wrong
thing, since those axes have no real implementation to back them yet. `eval/metrics.py`'s
`RepoScore` is renamed `RepoResult` and carries `config: EvalConfig` plus
`diff_line_jaccard`/`symbol_precision`/`symbol_recall`/`trace_path` as `| None` fields
(populated by later Phase 5 steps, not yet). `eval/harness.py`'s `run_repo()`/
`run_corpus()` take `config: EvalConfig` instead of `use_triage: bool`. `run_repo` also
writes real failure text + predicted class to a JSONL side-channel — the seed data
phase-4-triage.md's "≥100 hand-labelled failures" needed, now hand-labelled and closed
out (D55/D56). D62 made `tiers={"T1"}`/`{"T2","T3"}` real arms alongside the full set
(any other combination still raises `NotImplementedError` — `repair()` fuses T2/T3 into
one node, so a set naming one but not the other can't be honored). D63 (this step) added
`eval/store.py`'s `ResultStore`/`ResumeContext` (the SQLite result store, keyed by
`(repo_id, config_hash, corpus_sha)`, wired into `run_corpus` via its new `resume`
param) and `eval/manifest.py`'s `RunManifest`/`write_run_manifest` (the run manifest —
corpus sha256, prompt hashes, model, seed, agent git sha, start/end time). D64 (this step)
closed the `make eval` gap: `eval/run.py`'s `pmigrate eval run` (registered in `cli.py`,
also runnable as `python -m pmigrate.eval.run`) loads `configs/<name>.json` (JSON, not
YAML — round-trips through `EvalConfig.to_dict`/`from_dict` directly, no new dependency),
dispatches a real `ModelClient` via an explicit whitelist keyed by `config.model`
(`GeminiModelClient`/`GroqModelClient` — the only two real clients this project has),
wires up a real `DockerSandbox`, writes the run manifest before/after via
`eval/manifest.py`, and writes `docs/results/<config>.md` via the new
`eval/report.py`. Verified live end-to-end, including a real resumed second invocation
(D64's own decision entry has the numbers). Still missing from the full sketch:
parallelism over Docker, the `model_*` arm's Claude/GPT/local-Llama clients (`model_groq`
is the one real second-provider config today), and `docs/results/main.md`'s
cross-arm combination with bootstrap 95% CIs — phase-5-eval.md scopes CIs to that
combined report specifically, not to any single arm's own table.
