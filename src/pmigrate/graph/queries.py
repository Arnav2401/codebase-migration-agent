"""Cypher query text for store.py, kept in its own module (per PLAN.md's stated repo
layout) so the raw queries are readable and reviewable independent of the driver-calling
code around them. Every function returns (query, params) — never an f-string with
interpolated user data; repo_id/fqname/etc always travel as parameters, never inline, to
rule out Cypher injection from repo content the model or a repo's own source touches.

UNVERIFIED: written against the schema in docs/phase-1-graph.md and exercised only by
test_queries.py's string-shape assertions — never run against a live Neo4j instance in
this environment (Neo4j isn't installed here; see docs/phase-0-corpus.md). Run
`make neo4j` and the store.py integration test once it's available, before trusting this
against a real repo.

Schema (docs/phase-1-graph.md 1.3):
  (:Symbol {repo_id, fqname, kind, path, start_line, end_line}), unique on (repo_id, fqname)
  edges: CONTAINS | IMPORTS | INHERITS, each with {line: int | null, type_only: bool}
  (DECORATES/CALLS/REFERENCES are declared in EdgeKind but not populated — see build.py)
"""

from __future__ import annotations

from typing import Any

from pmigrate.types import EdgeKind, SymbolRef

Query = tuple[str, dict[str, Any]]

CONSTRAINT_QUERIES: tuple[str, ...] = (
    "CREATE CONSTRAINT symbol_repo_fqname IF NOT EXISTS "
    "FOR (s:Symbol) REQUIRE (s.repo_id, s.fqname) IS UNIQUE",
)


def upsert_symbols(refs: list[SymbolRef]) -> Query:
    rows = [
        {
            "repo_id": r.repo_id,
            "fqname": r.fqname,
            "kind": r.kind.value,
            "path": r.path,
            "start_line": r.start_line,
            "end_line": r.end_line,
        }
        for r in refs
    ]
    query = """
    UNWIND $rows AS row
    MERGE (s:Symbol {repo_id: row.repo_id, fqname: row.fqname})
    SET s.kind = row.kind, s.path = row.path,
        s.start_line = row.start_line, s.end_line = row.end_line
    """
    return query, {"rows": rows}


def upsert_edges_by_kind(repo_id: str, kind: EdgeKind, pairs: list[tuple[str, str]]) -> Query:
    """One call per EdgeKind. Cypher can't parameterize a relationship type, so the type
    is interpolated here — safe only because `kind` is a fixed, code-controlled EdgeKind
    member, never a value derived from repo content or model output; `pairs` (the actual
    untrusted-ish data — fqnames derived from a cloned repo's source) still travels as a
    parameter. Do not generalize this pattern to interpolate anything else."""
    rows = [{"src": src, "dst": dst} for src, dst in pairs]
    query = f"""
    UNWIND $rows AS row
    MATCH (a:Symbol {{repo_id: $repo_id, fqname: row.src}})
    MATCH (b:Symbol {{repo_id: $repo_id, fqname: row.dst}})
    MERGE (a)-[:{kind.value}]->(b)
    """
    return query, {"repo_id": repo_id, "rows": rows}


def get_symbol(repo_id: str, fqname: str) -> Query:
    query = "MATCH (s:Symbol {repo_id: $repo_id, fqname: $fqname}) RETURN s"
    return query, {"repo_id": repo_id, "fqname": fqname}


def _kinds_pattern(kinds: set[EdgeKind] | None) -> str:
    if not kinds:
        return ""
    return ":" + "|".join(k.value for k in kinds)


def dependents(repo_id: str, fqname: str, depth: int, kinds: set[EdgeKind] | None) -> Query:
    rel = _kinds_pattern(kinds)
    query = f"""
    MATCH (target:Symbol {{repo_id: $repo_id, fqname: $fqname}})
    MATCH (d:Symbol)-[{rel}*1..{depth}]->(target)
    WHERE d.repo_id = $repo_id
    RETURN DISTINCT d
    """
    return query, {"repo_id": repo_id, "fqname": fqname}


def dependencies(repo_id: str, fqname: str, depth: int, kinds: set[EdgeKind] | None) -> Query:
    rel = _kinds_pattern(kinds)
    query = f"""
    MATCH (source:Symbol {{repo_id: $repo_id, fqname: $fqname}})
    MATCH (source)-[{rel}*1..{depth}]->(d:Symbol)
    WHERE d.repo_id = $repo_id
    RETURN DISTINCT d
    """
    return query, {"repo_id": repo_id, "fqname": fqname}


def module_import_edges(repo_id: str) -> Query:
    """Fetched into Python and handed to toposort.py — see docs/phase-1-graph.md 1.4:
    Tarjan-in-Python over the edge list is the deliberate choice here, not Neo4j GDS."""
    query = """
    MATCH (a:Symbol {repo_id: $repo_id, kind: 'module'})-[:IMPORTS]->(b:Symbol {repo_id: $repo_id})
    RETURN a.fqname AS src, b.fqname AS dst
    """
    return query, {"repo_id": repo_id}


def all_module_fqnames(repo_id: str) -> Query:
    query = "MATCH (s:Symbol {repo_id: $repo_id, kind: 'module'}) RETURN s.fqname AS fqname"
    return query, {"repo_id": repo_id}
