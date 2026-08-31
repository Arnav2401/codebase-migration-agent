"""Neo4j-backed CodeGraph (docs/phase-1-graph.md 1.3). Same `build_symbol_graph()` pure
computation as memory_store.py — this file's only job is persisting and querying that data
via Cypher instead of Python dicts.

UNVERIFIED: Neo4j is not installed in this environment (docs/phase-0-corpus.md — "Also in
this phase"), so nothing here has run against a live database. Written carefully against
the schema and query text in queries.py (which at least has its string-shape checked by
test_queries.py), but treat this the way docs/phase-0-corpus.md's capture_baselines.py
treats its Docker code: real, not a stub, but not a claim of correctness until it's been
run for real. Bring up `make neo4j` and write an integration test — ingest the same
tests/graph/fixtures/sample_repo fixture already used by test_memory_store.py, and assert
the SAME results the in-memory backend gives — before trusting this against a real repo.
`topo_modules` deliberately fetches edges and sorts in Python (docs/phase-1-graph.md 1.4:
"Tarjan in Python over the edges is fine and clearer than fighting Neo4j GDS"), reusing
toposort.py rather than a second implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from neo4j import Driver

from pmigrate.graph.build import build_symbol_graph
from pmigrate.graph.protocol import IngestStats
from pmigrate.graph.queries import CONSTRAINT_QUERIES, upsert_edges_by_kind, upsert_symbols
from pmigrate.graph.queries import dependencies as dependencies_query
from pmigrate.graph.queries import dependents as dependents_query
from pmigrate.graph.queries import get_symbol as get_symbol_query
from pmigrate.graph.queries import module_import_edges as module_import_edges_query
from pmigrate.graph.repo_files import read_py_files
from pmigrate.graph.resolver import resolve_repo
from pmigrate.graph.token_budget import truncate_to_budget
from pmigrate.graph.toposort import topo_batches
from pmigrate.types import EdgeKind, RepoSpec, SymbolKind, SymbolRef


def _row_to_symbol_ref(row: dict[str, Any]) -> SymbolRef:
    return SymbolRef(
        repo_id=row["repo_id"],
        fqname=row["fqname"],
        kind=SymbolKind(row["kind"]),
        path=row["path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
    )


class Neo4jCodeGraph:
    """Implements the CodeGraph protocol (protocol.py) against a Neo4j instance."""

    def __init__(self, driver: Driver) -> None:
        self._driver = driver
        for query in CONSTRAINT_QUERIES:
            self._driver.execute_query(query)

    def ingest(self, repo: RepoSpec, root: Path) -> IngestStats:
        files = read_py_files(root)
        resolved = resolve_repo(files)
        data = build_symbol_graph(resolved, repo.repo_id)

        query, params = upsert_symbols(list(data.symbols.values()))
        self._driver.execute_query(query, **params)

        by_kind: dict[EdgeKind, list[tuple[str, str]]] = {}
        for edge in data.edges:
            by_kind.setdefault(edge.kind, []).append((edge.src_fqname, edge.dst_fqname))
        for kind, pairs in by_kind.items():
            query, params = upsert_edges_by_kind(repo.repo_id, kind, pairs)
            self._driver.execute_query(query, **params)

        return IngestStats(
            modules_parsed=len(resolved.modules),
            symbols_created=len(data.symbols),
            edges_created=len(data.edges),
            unresolved_imports=data.unresolved_imports,
            total_imports=data.total_imports,
            parse_errors=data.parse_errors,
        )

    def get(self, repo_id: str, fqname: str) -> SymbolRef | None:
        query, params = get_symbol_query(repo_id, fqname)
        result = self._driver.execute_query(query, **params)
        if not result.records:
            return None
        return _row_to_symbol_ref(dict(result.records[0]["s"]) | {"repo_id": repo_id})

    def dependents(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        query, params = dependents_query(ref.repo_id, ref.fqname, depth, kinds)
        result = self._driver.execute_query(query, **params)
        return [_row_to_symbol_ref(dict(r["d"]) | {"repo_id": ref.repo_id}) for r in result.records]

    def dependencies(
        self, ref: SymbolRef, *, depth: int = 1, kinds: set[EdgeKind] | None = None
    ) -> list[SymbolRef]:
        query, params = dependencies_query(ref.repo_id, ref.fqname, depth, kinds)
        result = self._driver.execute_query(query, **params)
        return [_row_to_symbol_ref(dict(r["d"]) | {"repo_id": ref.repo_id}) for r in result.records]

    def topo_modules(self, repo_id: str) -> list[list[str]]:
        query, params = module_import_edges_query(repo_id)
        result = self._driver.execute_query(query, **params)
        edges = [(r["src"], r["dst"]) for r in result.records]
        nodes = {n for edge in edges for n in edge}
        return topo_batches(nodes, edges)

    def neighbourhood(self, ref: SymbolRef, budget_tokens: int) -> list[SymbolRef]:
        candidates: list[SymbolRef] = []
        seen = {ref.fqname}
        for kind in (EdgeKind.INHERITS, EdgeKind.CONTAINS, EdgeKind.IMPORTS):
            for neighbour in self.dependents(ref, depth=2, kinds={kind}) + self.dependencies(
                ref, depth=2, kinds={kind}
            ):
                if neighbour.fqname not in seen:
                    seen.add(neighbour.fqname)
                    candidates.append(neighbour)
        return truncate_to_budget(candidates, budget_tokens)
