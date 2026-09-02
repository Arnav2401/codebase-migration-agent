"""T2 support functions for `agent/graph.py`'s `repair()` node: turning a failing test run
into (a) a prompt the model can act on and (b) a rewritten file extracted back out of its
response. Kept separate from graph.py so this logic is unit-testable without LangGraph
machinery, matching how `diff.py`/`patch.py` are already split out from the orchestration
layer.

Two real failure shapes drove `extract_target_file`'s two-strategy design (found against
real corpus tracebacks, not hypothesized):

1. A crash INSIDE first-party code (an import error, a bad type annotation at class-body
   evaluation time) puts a first-party, non-test path directly in the traceback — the
   deepest one before the trace drops into a third-party frame is the right target.
2. A `pydantic.ValidationError` raised when INSTANTIATING a model — the far more common T2
   case per PLAN.md's own framing (coercion/strictness changes) — does NOT: the traceback
   only shows the call site (often a test file, which must be excluded per I1) and pydantic
   internals. The class that actually needs fixing is never mentioned as a path at all.
   Pydantic's own error message names it directly ("N validation errors for ClassName"),
   so strategy 2 greps the repo for that class's definition instead of trusting the
   traceback's path list.
"""

from __future__ import annotations

import re
from pathlib import Path

import libcst as cst

from pmigrate.agent.patch import is_test_path
from pmigrate.graph.repo_files import read_py_files
from pmigrate.traceback_utils import deepest_first_party_frame
from pmigrate.triage.collect import collect_raw_failures
from pmigrate.types import TestRun

REPAIR_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "repair_system.md"

_VALIDATION_ERROR_CLASS = re.compile(r"validation errors? for (\w+)")
_CLASS_DEF = re.compile(r"^class (\w+)\b")
_FENCED_FILE_BLOCK = re.compile(r"File:\s*(\S+)\s*\n```(?:python)?\n(.*?)```", re.DOTALL)
_MODULE_NOT_FOUND = re.compile(r"ModuleNotFoundError: No module named")

# Pydantic/stdlib bases that are never going to be "the file that actually needs fixing" —
# excluded so find_related_files doesn't waste a repo-wide grep chasing them.
_NON_LOCAL_BASES = {"BaseModel", "BaseSettings", "object"}


def collect_failure_texts(run: TestRun) -> tuple[str, ...]:
    """Every piece of diagnostic text worth mining for a repair target, flattened —
    `triage/collect.py`'s `collect_raw_failures` computes the same underlying data but
    keeps each failure's node_id, which triage needs for classification and this
    single-prompt use case doesn't."""
    return tuple(f.text for f in collect_raw_failures(run))


def _find_class_definitions(
    class_names: set[str], repo_root: Path, *, exclude_path: str | None = None
) -> dict[str, str]:
    """Repo-wide grep for `class <Name>` definitions, first match per name wins. Shared
    by `extract_target_file`'s strategy 2 and `find_related_files` — both are answering
    the same underlying question ("where is this class actually defined"), just starting
    from a different clue (an error message's class name vs. another file's base list)."""
    found: dict[str, str] = {}
    remaining = set(class_names)
    if not remaining:
        return found
    for path, content in sorted(read_py_files(repo_root).items()):
        if path == exclude_path or is_test_path(path):
            continue
        for line in content.decode("utf-8", errors="replace").splitlines():
            defined = _CLASS_DEF.match(line)
            if defined is not None and defined.group(1) in remaining:
                found[defined.group(1)] = path
                remaining.discard(defined.group(1))
        if not remaining:
            break
    return found


def extract_target_file(failure_texts: tuple[str, ...], repo_root: Path) -> str | None:
    """See module docstring for the two strategies. Returns a path relative to
    `repo_root`, or None if neither strategy finds a first-party, non-test candidate.

    Failure texts whose root cause is a missing third-party module are excluded before
    either strategy runs. Found live (docs/decisions.md D26): a `ModuleNotFoundError` for
    a package that was simply never installed (`fastapi_plugins/memcached.py` importing
    `aiomcache`) still has a legitimate first-party frame in its traceback — the file
    contains a deliberate `raise RuntimeError(...)` guard for exactly this case, so
    strategy 1 finds it as if it were a real bug. No source rewrite fixes a package that
    isn't installed (this is `FailureClass.THIRD_PARTY_PIN`, docs/interfaces.md §6, a
    corpus/environment gap already tracked in D20/D23) — repair() would otherwise spend
    real money "fixing" a file that was never broken.
    """
    failure_texts = tuple(t for t in failure_texts if not _MODULE_NOT_FOUND.search(t))
    combined = "\n".join(failure_texts)
    if not combined.strip():
        return None

    target = deepest_first_party_frame(combined)
    if target is not None:
        return target

    class_match = _VALIDATION_ERROR_CLASS.search(combined)
    if class_match is None:
        return None
    class_name = class_match.group(1)
    return _find_class_definitions({class_name}, repo_root).get(class_name)


def _base_class_names(source: str) -> set[str]:
    """Every base-class name a top-level class in `source` inherits from, qualified
    names reduced to their final component (`fastapi_plugins.RedisSettings` ->
    `RedisSettings`) — enough to search for a definition BY NAME. Full import
    resolution is `graph/resolver.py`'s job, deliberately not wired in here
    (docs/decisions.md D25's "no graph-retrieved context" scoping still holds; this is a
    narrower, local heuristic, not that).
    """
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, cst.ClassDef):
            continue
        for arg in node.bases:
            value = arg.value
            if isinstance(value, cst.Name):
                names.add(value.value)
            elif isinstance(value, cst.Attribute) and isinstance(value.attr, cst.Name):
                names.add(value.attr.value)
    return names - _NON_LOCAL_BASES


def find_related_files(target_path: str, before: str, repo_root: Path) -> tuple[str, ...]:
    """Files the target file's own classes inherit from, when that base isn't defined
    locally. Found live (docs/decisions.md D26/D28): T2 correctly identified
    `demo.py` as the file mentioned in a `ValidationError`, produced a clean rewrite of
    it, but the actual broken fields (`redis_url` etc.) are declared on `RedisSettings`
    — imported from `fastapi_plugins`, defined in `fastapi_plugins/_redis.py` — which
    `demo.py`'s `AppSettings` only inherits, declaring none of those fields itself. No
    rewrite of the file named in an error can fix a field declared in a DIFFERENT file
    it merely composes or inherits.
    """
    base_names = _base_class_names(before)
    if not base_names:
        return ()
    found = _find_class_definitions(base_names, repo_root, exclude_path=target_path)
    return tuple(sorted(set(found.values())))


def build_repair_prompt(files: dict[str, str], failure_texts: tuple[str, ...]) -> str:
    file_blocks = "\n\n".join(
        f"File: {path}\n\n```python\n{content}\n```" for path, content in files.items()
    )
    failures = "\n\n---\n\n".join(failure_texts)
    return f"{file_blocks}\n\nFailing test output:\n\n{failures}\n"


def extract_rewritten_files(response_text: str) -> dict[str, str]:
    """Parses one or more `File: <path>` + fenced-block pairs out of the model's
    response. A single-file response (the common case) is just a dict of length 1 —
    callers don't need a separate code path for "one file" vs "several"."""
    return {path: content for path, content in _FENCED_FILE_BLOCK.findall(response_text)}


def repair_system_prompt() -> str:
    return REPAIR_SYSTEM_PROMPT_PATH.read_text()
