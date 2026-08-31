"""Query-text-shape tests only — there's no live Neo4j in this environment (see
docs/phase-0-corpus.md), so these can't verify the Cypher actually runs. What they DO
verify: repo-controlled values (fqnames, repo_id) never get interpolated into the query
string — they must always travel as $params, since a repo's own file paths / symbol names
are attacker-influenceable input once Phase 3 starts editing real GitHub repos.
"""

from pmigrate.graph.queries import (
    dependencies,
    dependents,
    get_symbol,
    module_import_edges,
    upsert_edges_by_kind,
    upsert_symbols,
)
from pmigrate.types import EdgeKind, SymbolKind, SymbolRef


def test_upsert_symbols_uses_params_not_interpolation() -> None:
    ref = SymbolRef(
        repo_id="'; DROP ALL",
        fqname="app.models.user.User",
        kind=SymbolKind.CLASS,
        path="app/models/user.py",
        start_line=1,
        end_line=5,
    )
    query, params = upsert_symbols([ref])
    assert "DROP ALL" not in query
    assert params["rows"][0]["repo_id"] == "'; DROP ALL"
    assert "UNWIND $rows" in query


def test_upsert_edges_by_kind_interpolates_only_the_fixed_enum() -> None:
    query, params = upsert_edges_by_kind(
        "repo", EdgeKind.IMPORTS, [("a.b", "a.c"), ("'; DROP ALL", "x")]
    )
    assert "IMPORTS" in query
    assert "DROP ALL" not in query  # the malicious-looking fqname must be in params, not the query
    assert params["rows"][1]["src"] == "'; DROP ALL"


def test_get_symbol_params() -> None:
    query, params = get_symbol("repo", "a.b.C")
    assert params == {"repo_id": "repo", "fqname": "a.b.C"}
    assert "$repo_id" in query and "$fqname" in query


def test_dependents_and_dependencies_respect_kind_filter() -> None:
    query, _ = dependents("repo", "a.b.C", depth=2, kinds={EdgeKind.INHERITS})
    assert "INHERITS" in query
    assert "*1..2" in query

    query2, _ = dependencies("repo", "a.b.C", depth=1, kinds=None)
    assert "*1..1" in query2


def test_module_import_edges_params() -> None:
    _, params = module_import_edges("repo")
    assert params == {"repo_id": "repo"}
