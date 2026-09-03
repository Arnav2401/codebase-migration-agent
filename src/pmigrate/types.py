"""Shared contracts between pmigrate components.

This module is the seam described in docs/interfaces.md: components talk to each other
only through these types, never through each other's internals. If a phase needs a new
field, add it here first and update docs/interfaces.md in the same change — don't let the
two drift.

Only the types Phase 0 actually uses (RepoSpec, BaselineResult, DiffStats) have real
fields filled in from decisions made so far. Later phases' types are transcribed from
docs/interfaces.md as declarations to code against; expect to adjust them as each phase is
actually built — treat them as a starting contract, not a finished one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

# ---------------------------------------------------------------------------
# Phase 0 — corpus (docs/interfaces.md §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiffStats:
    """Shape of the human's migration commit, used as ground truth in Phase 5."""

    files_changed: int
    lines_added: int
    lines_removed: int
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class BaselineResult:
    """Captured by running the test suite at pre_sha under pydantic v1.

    `passed` is the only honest scoring denominator (invariant I4, PLAN.md §2) — a repo's
    own pre-existing failures must never count against or for the agent.
    """

    passed: frozenset[str]
    failed: frozenset[str]
    skipped: frozenset[str]
    flaky: frozenset[str]  # disagreed between the two baseline-capture runs; excluded
    duration_s: float


@dataclass(frozen=True)
class RepoSpec:
    """One corpus entry. `corpus/manifest.json` is a list of these, hand-curated and
    committed — see docs/phase-0-corpus.md for how entries get here."""

    repo_id: str  # "org__name", filesystem/image safe
    url: str
    pre_sha: str  # parent of the human migration commit
    post_sha: str  # the human migration commit itself
    python_version: str  # e.g. "3.11"
    install_cmd: tuple[str, ...]
    test_cmd: tuple[str, ...]
    setup_overrides: tuple[str, ...] = ()  # extra shell lines injected into the Dockerfile
    split: Literal["dev", "test"] = "dev"
    baseline: BaselineResult | None = None  # filled in by capture_baselines
    human_diff_stats: DiffStats | None = None  # filled in by validate


# ---------------------------------------------------------------------------
# Phase 1 — graph (docs/interfaces.md §2). Declared now so Phase 0 tooling can
# reference SymbolRef in type signatures without a circular dependency later.
# ---------------------------------------------------------------------------


class SymbolKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    ASSIGNMENT = "assignment"


@dataclass(frozen=True)
class SymbolRef:
    repo_id: str
    fqname: str
    kind: SymbolKind
    path: str
    start_line: int
    end_line: int


class EdgeKind(StrEnum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    REFERENCES = "REFERENCES"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    DECORATES = "DECORATES"


@dataclass(frozen=True)
class MigrationUnit:
    module: str
    path: str
    symbols: tuple[SymbolRef, ...]
    signals: frozenset[str]
    est_difficulty: int  # 0-3


# ---------------------------------------------------------------------------
# Phase 2 — sandbox (docs/interfaces.md §3)
# ---------------------------------------------------------------------------


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
class ImageRef:
    """Referenced but not typed in docs/interfaces.md §3 — defined here since Sandbox.build
    returns one and Sandbox.run_tests consumes it. Carries the cache-key components
    (docs/phase-2-sandbox.md "Image caching") alongside the tag so a caller can verify a
    reused image still matches what it thinks it's running, not just trust the tag string.

    Also carries `test_cmd`: interfaces.md's `run_tests(image, workdir_overlay, policy,
    selection)` signature has no RepoSpec parameter, so the test command has to travel
    with the image reference rather than being re-supplied per call or stashed as hidden
    state on the Sandbox instance."""

    tag: str
    repo_id: str
    sha: str
    pydantic: Literal["v1", "v2"]
    deps_hash: str
    test_cmd: tuple[str, ...]


@dataclass(frozen=True)
class TestOutcome:
    node_id: str
    status: Literal["passed", "failed", "error", "skipped", "xfailed"]
    duration_s: float
    message: str | None
    traceback: str | None
    captured_stdout: str | None


@dataclass(frozen=True)
class TestRun:
    outcomes: tuple[TestOutcome, ...]
    collection_errors: tuple[str, ...]
    exit_code: int
    duration_s: float
    truncated: bool


# ---------------------------------------------------------------------------
# Phase 4 — triage (docs/interfaces.md §6)
# ---------------------------------------------------------------------------


class FailureClass(StrEnum):
    IMPORT_ERROR = "import_error"
    CLASS_DEF_ERROR = "class_def_error"
    REMOVED_API = "removed_api"
    VALIDATION_BEHAVIOUR = "validation_behaviour"
    SERIALIZATION_DIFF = "serialization_diff"
    ERROR_MESSAGE_DIFF = "error_message_diff"
    THIRD_PARTY_PIN = "third_party_pin"
    PREEXISTING = "preexisting"
    FLAKY = "flaky"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Diagnosis:
    node_ids: tuple[str, ...]
    cls: FailureClass
    confidence: float
    evidence: str
    suspect_symbols: tuple[SymbolRef, ...]
    strategy: str


# ---------------------------------------------------------------------------
# Phase 6 — trace (docs/interfaces.md §7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TraceEvent:
    run_id: str
    span_id: str
    parent_span: str | None
    ts: float
    kind: Literal["phase", "llm_call", "tool_call", "patch", "test_run", "triage", "error"]
    payload: dict[str, object]
    tokens_in: int | None = None
    tokens_out: int | None = None
    usd: float | None = None
