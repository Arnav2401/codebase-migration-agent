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
