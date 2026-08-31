"""Pure construction of the SymbolRef-level graph (docs/interfaces.md §2) from a
ResolvedRepo. Shared by every CodeGraph backend (memory_store.py, store.py) so the actual
graph-building logic — deciding what nodes and edges exist — is written and tested exactly
once; a backend's only job is to persist and query whatever this produces.

Scope, stated plainly rather than silently partial: of the six EdgeKinds in
docs/interfaces.md §2, this builds three.
  - CONTAINS  — module -> class -> method, module -> function, class -> nested class.
    Trivial and exact: it falls straight out of the IR's tree structure.
  - IMPORTS   — module -> module, first-party only, taken directly from resolver.py's
    edges. (Third-party imports still matter — that's what
    `relevance.import_edges_touching` answers directly against the ResolvedRepo — but a
    third-party module was never ingested, so it has no SymbolRef to point an edge at.)
  - INHERITS  — class -> first-party base class, via the same base-resolution logic
    relevance.py uses for BaseModel detection (`resolve_base_targets`). Inheriting from a
    pydantic base itself doesn't get an edge here for the same reason third-party IMPORTS
    doesn't: there's no first-party SymbolRef for `pydantic.BaseModel`. relevance.py's own
    closure (tested independently) is what actually answers "does this transitively
    subclass BaseModel" — the graph's INHERITS edges are for first-party-to-first-party
    class hierarchies (e.g. an app's own abstract base models).
  - DECORATES and CALLS/REFERENCES are NOT built. DECORATES would mostly point at
    third-party decorators (`@validator`) for the same reason above, and decorator names
    are already on ParsedFunction/ParsedClass which relevance.py reads directly — no graph
    edge needed for what Phase 1 currently uses. CALLS/REFERENCES (one first-party symbol
    calling/using another) needs scope-aware name resolution — is `helper()` a local
    import, a same-module function, a method on `self`? — that hasn't been built. Call
    sites ARE captured as raw text in the IR (ParsedCall.callee_text) for relevance
    signal detection; resolving them to a target SymbolRef is a real follow-up, not
    something dependents()/dependencies() can answer today for CALLS specifically.
"""

from __future__ import annotations

from dataclasses import dataclass

from pmigrate.graph.relevance import resolve_base_targets
from pmigrate.graph.resolver import ResolvedRepo
from pmigrate.types import EdgeKind, SymbolKind, SymbolRef


@dataclass(frozen=True)
class GraphEdge:
    src_fqname: str
    dst_fqname: str
    kind: EdgeKind


@dataclass(frozen=True)
class SymbolGraphData:
    symbols: dict[str, SymbolRef]  # fqname -> SymbolRef, single repo
    edges: tuple[GraphEdge, ...]
    module_import_edges: tuple[tuple[str, str], ...]  # (importer, imported) module fqnames
    unresolved_imports: int
    total_imports: int
    parse_errors: tuple[str, ...]


def build_symbol_graph(resolved: ResolvedRepo, repo_id: str) -> SymbolGraphData:
    symbols: dict[str, SymbolRef] = {}
    edges: list[GraphEdge] = []

    def add_symbol(fqname: str, kind: SymbolKind, path: str, start: int, end: int) -> None:
        symbols[fqname] = SymbolRef(
            repo_id=repo_id, fqname=fqname, kind=kind, path=path, start_line=start, end_line=end
        )

    for fq, module in resolved.modules.items():
        path = resolved.module_paths[fq]
        add_symbol(fq, SymbolKind.MODULE, path, 1, 1)

        for fn in module.functions:
            fn_fq = f"{fq}.{fn.name}"
            add_symbol(fn_fq, SymbolKind.FUNCTION, path, fn.start_line, fn.end_line)
            edges.append(GraphEdge(fq, fn_fq, EdgeKind.CONTAINS))

        for cls in module.classes:
            cls_fq = f"{fq}.{cls.name}"
            add_symbol(cls_fq, SymbolKind.CLASS, path, cls.start_line, cls.end_line)
            edges.append(GraphEdge(fq, cls_fq, EdgeKind.CONTAINS))

            for method in cls.methods:
                method_fq = f"{cls_fq}.{method.name}"
                add_symbol(method_fq, SymbolKind.METHOD, path, method.start_line, method.end_line)
                edges.append(GraphEdge(cls_fq, method_fq, EdgeKind.CONTAINS))

            for nested in cls.nested_classes:
                nested_fq = f"{cls_fq}.{nested.name}"
                add_symbol(nested_fq, SymbolKind.CLASS, path, nested.start_line, nested.end_line)
                edges.append(GraphEdge(cls_fq, nested_fq, EdgeKind.CONTAINS))
                for method in nested.methods:
                    method_fq = f"{nested_fq}.{method.name}"
                    add_symbol(
                        method_fq, SymbolKind.METHOD, path, method.start_line, method.end_line
                    )
                    edges.append(GraphEdge(nested_fq, method_fq, EdgeKind.CONTAINS))

    module_import_edges: list[tuple[str, str]] = []
    for edge in resolved.import_edges:
        if edge.is_first_party and edge.from_module in symbols and edge.to_module in symbols:
            edges.append(GraphEdge(edge.from_module, edge.to_module, EdgeKind.IMPORTS))
            module_import_edges.append((edge.from_module, edge.to_module))

    for fq, module in resolved.modules.items():
        for cls in module.classes:
            cls_fq = f"{fq}.{cls.name}"
            for target in resolve_base_targets(fq, cls, resolved.modules):
                if isinstance(target, tuple):
                    base_fq = f"{target[0]}.{target[1]}"
                    if base_fq in symbols:
                        edges.append(GraphEdge(cls_fq, base_fq, EdgeKind.INHERITS))

    parse_errors = tuple(
        resolved.module_paths[fq] for fq, m in resolved.modules.items() if m.has_syntax_errors
    )

    return SymbolGraphData(
        symbols=symbols,
        edges=tuple(edges),
        module_import_edges=tuple(module_import_edges),
        unresolved_imports=resolved.unresolved_count,
        total_imports=resolved.total_import_count,
        parse_errors=parse_errors,
    )
