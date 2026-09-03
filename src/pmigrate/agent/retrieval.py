"""Phase 5's retrieval ablation (docs/phase-5-eval.md): what context does `repair()`
include alongside the target file when building its prompt? Three arms; `graph` and
`wholefile` here, `embedding` a separate, later step -- no embedding/vector library exists
in this project yet, and picking a provider is a real decision on its own.

`Retrieval.related_files` matches `agent/repair.py`'s `find_related_files` exactly in
shape (same three params, same "extra file paths, not including target_path" contract) --
that function IS the default strategy (docs/decisions.md D28's grep heuristic), preserved
as `build_migration_graph`'s fallback when no `retrieval` is passed, so every existing
test keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pmigrate.graph.memory_store import InMemoryCodeGraph
from pmigrate.graph.relevance import find_pydantic_model_classes
from pmigrate.graph.repo_files import read_py_files
from pmigrate.graph.resolver import resolve_repo
from pmigrate.graph.token_budget import truncate_to_budget
from pmigrate.types import RepoSpec, SymbolKind, SymbolRef

# Matches graph/memory_store.py's neighbourhood() default shape -- both budgets estimate
# from the same TOKENS_PER_LINE_ESTIMATE (token_budget.py), so this stays comparable
# across the two strategies rather than an arbitrarily different number per arm.
DEFAULT_BUDGET_TOKENS = 4000


class Retrieval(Protocol):
    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        """Extra file paths (relative to `repo_root`, NOT including `target_path`) to
        include as context in the repair prompt alongside the target file."""
        ...


@dataclass
class GraphRetrieval:
    """docs/phase-5-eval.md's "graph" arm -- wraps `CodeGraph.neighbourhood`
    (graph/protocol.py), whose own docstring calls it "the function Phase 5's retrieval
    ablation swaps out." Re-ingests a fresh `InMemoryCodeGraph` on every call rather than
    caching one, since `repo_root`'s content changes between `repair()` iterations as
    earlier edits land -- matching `find_related_files`'s own always-fresh-read behavior,
    not an oversight. Seeds the BFS from the target file's own MODULE symbol (CONTAINS
    edges reach its classes, IMPORTS edges reach imported modules) rather than one
    specific class, since a target FILE, not a single symbol, is what repair() actually
    wants context for."""

    repo_id: str
    budget_tokens: int = DEFAULT_BUDGET_TOKENS

    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        resolved = resolve_repo(read_py_files(repo_root))
        module_fqname = next(
            (fq for fq, path in resolved.module_paths.items() if path == target_path), None
        )
        if module_fqname is None:
            return ()

        graph = InMemoryCodeGraph()
        # ingest() only ever reads repo.repo_id off this argument (graph/memory_store.py)
        # -- every other RepoSpec field is meaningless for a one-off graph population
        # call, not a real corpus entry, so placeholders are correct here, not a shortcut.
        graph.ingest(
            RepoSpec(
                repo_id=self.repo_id,
                url="",
                pre_sha="",
                post_sha="",
                python_version="",
                install_cmd=(),
                test_cmd=(),
            ),
            repo_root,
        )

        target_ref = graph.get(self.repo_id, module_fqname)
        if target_ref is None:
            return ()

        neighbours = graph.neighbourhood(target_ref, self.budget_tokens)
        paths = {n.path for n in neighbours if n.path != target_path}
        return tuple(sorted(paths))


@dataclass
class WholefileRetrieval:
    """docs/phase-5-eval.md's "wholefile" arm -- every pydantic-touching file (the same
    signal `graph/relevance.py`'s `find_pydantic_model_classes` gives `compute_work_list`
    for T1's own file selection), truncated to a token budget via the same
    `truncate_to_budget` `GraphRetrieval` uses -- applied to whole files (start_line=1,
    end_line=file length) instead of graph neighbours. Answers phase-5-eval.md's own
    question: "is retrieval needed at all, or does a big context window solve it?"."""

    budget_tokens: int = DEFAULT_BUDGET_TOKENS

    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        files = read_py_files(repo_root)
        resolved = resolve_repo(files)
        model_classes = find_pydantic_model_classes(resolved)
        touched_paths = sorted(
            {resolved.module_paths[fq] for fq, _cls_name in model_classes} - {target_path}
        )

        candidates = []
        for path in touched_paths:
            content = files.get(path, b"").decode("utf-8", errors="replace")
            line_count = len(content.splitlines()) or 1
            candidates.append(
                SymbolRef(
                    repo_id="",
                    fqname=path,
                    kind=SymbolKind.MODULE,
                    path=path,
                    start_line=1,
                    end_line=line_count,
                )
            )

        return tuple(c.path for c in truncate_to_budget(candidates, self.budget_tokens))
