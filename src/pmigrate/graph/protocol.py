"""The CodeGraph contract from docs/interfaces.md §2, defined once so every backend
(in-memory, Neo4j, whatever comes next per decisions.md D2) implements the same shape.
Query implementations live in each backend; this module only fixes the interface and the
one small data type (`IngestStats`) both backends return.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pmigrate.types import EdgeKind, RepoSpec, SymbolRef


@dataclass(frozen=True)
class IngestStats:
    modules_parsed: int
    symbols_created: int
    edges_created: int
    unresolved_imports: int
    total_imports: int
    parse_errors: tuple[str, ...]  # repo-relative paths that had syntax errors

    @property
    def resolution_coverage(self) -> float:
        if self.total_imports == 0:
            return 1.0
        return 1 - (self.unresolved_imports / self.total_imports)


class CodeGraph(Protocol):
    def ingest(self, repo: RepoSpec, root: Path) -> IngestStats: ...

    def get(self, repo_id: str, fqname: str) -> SymbolRef | None: ...

    def dependents(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        """Who would break if `ref` changed — incoming REFERENCES/CALLS/IMPORTS/INHERITS."""
        ...

    def dependencies(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        """What `ref` needs — outgoing edges."""
        ...

    def topo_modules(self, repo_id: str) -> list[list[str]]:
        """Modules in migration order, leaves first. Inner lists are SCCs — members of a
        circular-import group must migrate together (see toposort.py)."""
        ...

    def neighbourhood(self, ref: SymbolRef, budget_tokens: int) -> list[SymbolRef]:
        """Context selection for a prompt: ranked BFS out from ref, truncated to a token
        budget. This is the function Phase 5's retrieval ablation swaps out."""
        ...
