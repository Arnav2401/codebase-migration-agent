"""In-memory CodeGraph backend. Not in the original PLAN.md file layout — added during
Phase 1 implementation and worth flagging as a deliberate addition, not a silent
improvisation: decisions.md D2 explicitly pre-approved exactly this swap ("If Neo4j
becomes friction, the in-memory networkx backend is a 1-day swap and the interfaces don't
change... don't let it block Phase 3"). Neo4j isn't installed in this environment, so this
is the backend that's actually exercised by the test suite end-to-end; store.py (Neo4j) is
written against the same CodeGraph protocol and the same build_symbol_graph() data, but is
unverified against a live database. This file has no Neo4j dependency and no external
service — everything is plain Python dicts, which is also just... fine, for repo-scale
graphs; nothing here claims to need to scale further than that.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from pmigrate.graph.build import build_symbol_graph
from pmigrate.graph.protocol import IngestStats
from pmigrate.graph.repo_files import read_py_files
from pmigrate.graph.resolver import resolve_repo
from pmigrate.graph.token_budget import truncate_to_budget
from pmigrate.graph.toposort import topo_batches
from pmigrate.types import EdgeKind, RepoSpec, SymbolKind, SymbolRef


class InMemoryCodeGraph:
    """Implements the CodeGraph protocol (protocol.py) — see that module for the
    contract. Holds symbols and edges for possibly multiple repos, namespaced by repo_id."""

    def __init__(self) -> None:
        self._symbols: dict[tuple[str, str], SymbolRef] = {}
        self._outgoing: dict[tuple[str, str], list[tuple[SymbolRef, EdgeKind]]] = defaultdict(list)
        self._incoming: dict[tuple[str, str], list[tuple[SymbolRef, EdgeKind]]] = defaultdict(list)
        self._module_import_edges: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._modules: dict[str, set[str]] = defaultdict(set)

    def ingest(self, repo: RepoSpec, root: Path) -> IngestStats:
        files = read_py_files(root)
        resolved = resolve_repo(files)
        data = build_symbol_graph(resolved, repo.repo_id)

        for fq, ref in data.symbols.items():
            self._symbols[(repo.repo_id, fq)] = ref
            if ref.kind == SymbolKind.MODULE:
                self._modules[repo.repo_id].add(fq)

        for edge in data.edges:
            src = data.symbols[edge.src_fqname]
            dst = data.symbols[edge.dst_fqname]
            self._outgoing[(repo.repo_id, edge.src_fqname)].append((dst, edge.kind))
            self._incoming[(repo.repo_id, edge.dst_fqname)].append((src, edge.kind))

        self._module_import_edges[repo.repo_id].extend(data.module_import_edges)

        return IngestStats(
            modules_parsed=len(resolved.modules),
            symbols_created=len(data.symbols),
            edges_created=len(data.edges),
            unresolved_imports=data.unresolved_imports,
            total_imports=data.total_imports,
            parse_errors=data.parse_errors,
        )

    def get(self, repo_id: str, fqname: str) -> SymbolRef | None:
        return self._symbols.get((repo_id, fqname))

    def _bfs(
        self,
        ref: SymbolRef,
        adjacency: dict[tuple[str, str], list[tuple[SymbolRef, EdgeKind]]],
        depth: int,
        kinds: set[EdgeKind] | None,
    ) -> list[SymbolRef]:
        visited = {ref.fqname}
        result: list[SymbolRef] = []
        frontier = [ref.fqname]
        for _ in range(depth):
            next_frontier = []
            for fq in frontier:
                for neighbour, kind in adjacency.get((ref.repo_id, fq), []):
                    if kinds is not None and kind not in kinds:
                        continue
                    if neighbour.fqname in visited:
                        continue
                    visited.add(neighbour.fqname)
                    result.append(neighbour)
                    next_frontier.append(neighbour.fqname)
            frontier = next_frontier
            if not frontier:
                break
        return result

    def dependents(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        return self._bfs(ref, self._incoming, depth, kinds)

    def dependencies(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        return self._bfs(ref, self._outgoing, depth, kinds)

    def topo_modules(self, repo_id: str) -> list[list[str]]:
        nodes = self._modules.get(repo_id, set())
        edges = self._module_import_edges.get(repo_id, [])
        return topo_batches(nodes, edges)

    def neighbourhood(self, ref: SymbolRef, budget_tokens: int) -> list[SymbolRef]:
        """Ranked BFS truncated to an estimated token budget. Ranking order — bases first,
        then structural containment/import neighbours — reflects what's actually built
        (see build.py's docstring for what's NOT built: no CALLS/REFERENCES, so a "callers"
        tier doesn't exist yet)."""
        ranked_kinds = [EdgeKind.INHERITS, EdgeKind.CONTAINS, EdgeKind.IMPORTS]
        seen = {ref.fqname}
        candidates: list[SymbolRef] = []
        for kind in ranked_kinds:
            for neighbour in self.dependents(ref, depth=2, kinds={kind}) + self.dependencies(
                ref, depth=2, kinds={kind}
            ):
                if neighbour.fqname not in seen:
                    seen.add(neighbour.fqname)
                    candidates.append(neighbour)

        return truncate_to_budget(candidates, budget_tokens)
