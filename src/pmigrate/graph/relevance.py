"""Phase 1 step 1.5 (docs/phase-1-graph.md) — which symbols actually need migrating, and
in what order. `compute_work_list` IS the agent's plan (docs/phase-1-graph.md: "The
retrieval layer produces the *task list*, not just context. That's the point.").

Interface note (a real deviation from the original sketch in docs/interfaces.md §2,
worth flagging rather than quietly working around): `work_list(graph: CodeGraph, repo_id)`
assumed the graph alone carried enough information. In practice, signal detection needs
decorator names, call sites, and Field() kwargs — the parsed IR — which a CodeGraph (Neo4j
or otherwise) has no reason to store once it's built the node/edge structure. Re-deriving
that from graph queries would mean either bloating every Symbol node with parser-specific
properties, or re-parsing at query time and losing the "ingest once, query many times"
property Phase 5 depends on for repeated eval runs. So `compute_work_list` here operates
directly on a `ResolvedRepo` (resolver.py's output) instead of a `CodeGraph`. Worth deciding
deliberately once store.py's ingest() is wired up for real: either CodeGraph grows a
`signals(ref) -> frozenset[str]` query backed by properties computed at ingest time, or
Phase 3's planner keeps the ResolvedRepo around alongside the graph. Not resolved here.

BaseModel/BaseSettings detection is a transitive closure over first-party class hierarchies
(a class can subclass an intermediate first-party class that itself subclasses BaseModel),
computed as a fixed-point over direct base references — no Neo4j required, since this is
exactly the same kind of graph-over-an-edge-list problem toposort.py already solves for
modules. `pydantic.BaseModel`-style dotted-attribute bases are matched by name only (no
resolution of what `pydantic` was bound to) — a deliberate, cheap heuristic; see
docs/phase-1-graph.md "Pitfalls": dynamic Python is unresolvable, measure it, don't chase it.

Known gap, stated rather than silently dropped: `__fields__` / `__config__` accessed as a
bare attribute (not a call, e.g. `for name in Model.__fields__:`) isn't detected — the
parser's call-site scan only sees `call` nodes, and `update_forward_refs()` (always called)
IS covered. Adding bare-attribute detection would need either a raw-text fallback scan (the
IR doesn't retain source bytes) or a broader AST attribute-access pass; left as a follow-up.
"""

from __future__ import annotations

from pmigrate.graph.ir import ParsedClass, ParsedModule
from pmigrate.graph.resolver import ImportEdge, ResolvedRepo, resolve_import_target
from pmigrate.graph.toposort import topo_batches
from pmigrate.types import MigrationUnit, SymbolKind, SymbolRef

ClassKey = tuple[str, str]  # (module_fqname, class_name) — a class doesn't get a graph
# fqname of its own in the IR (only SymbolRef does, once we know it's relevant), so this
# pair is the identity used for the closure below.

_PYDANTIC_MODULES = frozenset({"pydantic", "pydantic.main", "pydantic.v1", "pydantic_settings"})
_V1_VALIDATOR_DECORATORS = frozenset({"validator", "root_validator"})
_MECHANICAL_CALL_NAMES = frozenset(
    {"dict", "json", "parse_obj", "parse_raw", "copy", "update_forward_refs"}
)
_V1_FIELD_KWARGS = frozenset(
    {"regex", "allow_mutation", "const", "min_items", "max_items", "unique_items"}
)

_DIFFICULTY = {
    "BaseModel": 1,
    "BaseSettings": 1,
    "Config": 1,
    "mechanical_call": 1,
    "field_v1_kwargs": 2,
    "validator": 2,
    "custom_get_validators": 3,
}


def resolve_base_targets(
    module_fqname: str, cls: ParsedClass, modules: dict[str, ParsedModule]
) -> list[str | ClassKey]:
    module = modules[module_fqname]
    results: list[str | ClassKey] = []
    for base in cls.bases:
        if "." in base:
            _, _, tail = base.rpartition(".")
            if tail in ("BaseModel", "BaseSettings"):
                results.append(tail)
                continue

        matched = False
        for imp in module.imports:
            if imp.imported_as != base or imp.original_name == "*":
                continue
            target = resolve_import_target(module_fqname, imp, modules)
            if target in _PYDANTIC_MODULES and imp.original_name in ("BaseModel", "BaseSettings"):
                results.append(imp.original_name)
                matched = True
            elif target is not None:
                results.append((target, imp.original_name or base))
                matched = True
            break
        if matched:
            continue

        if any(c.name == base for c in module.classes):
            results.append((module_fqname, base))

    return results


def find_pydantic_model_classes(resolved: ResolvedRepo) -> dict[ClassKey, str]:
    """(module_fqname, class_name) -> "BaseModel" | "BaseSettings" for every first-party
    class that transitively subclasses one of them."""
    direct: dict[ClassKey, list[str | ClassKey]] = {}
    for fq, module in resolved.modules.items():
        for cls in module.classes:
            direct[(fq, cls.name)] = resolve_base_targets(fq, cls, resolved.modules)

    is_model: dict[ClassKey, str] = {}
    changed = True
    while changed:
        changed = False
        for key, targets in direct.items():
            if key in is_model:
                continue
            for t in targets:
                if isinstance(t, str):
                    is_model[key] = t
                    changed = True
                    break
                if t in is_model:
                    is_model[key] = is_model[t]
                    changed = True
                    break
    return is_model


def _mechanical_call_signals(calls) -> set[str]:  # type: ignore[no-untyped-def]
    signals = set()
    for call in calls:
        leaf = call.callee_text.rsplit(".", 1)[-1]
        if leaf in _MECHANICAL_CALL_NAMES:
            signals.add("mechanical_call")
        if leaf == "Field" and any(k in _V1_FIELD_KWARGS for k in call.kwargs):
            signals.add("field_v1_kwargs")
        if leaf in ("constr", "conint", "condecimal", "confloat") and any(
            k in _V1_FIELD_KWARGS for k in call.kwargs
        ):
            signals.add("field_v1_kwargs")
    return signals


def class_signals(cls: ParsedClass, is_pydantic_base: str | None) -> frozenset[str]:
    signals: set[str] = set()
    if is_pydantic_base:
        signals.add(is_pydantic_base)
    if any(nested.name == "Config" for nested in cls.nested_classes):
        signals.add("Config")
    for method in cls.methods:
        if method.name == "__get_validators__":
            signals.add("custom_get_validators")
        if any(d in _V1_VALIDATOR_DECORATORS for d in method.decorators):
            signals.add("validator")
        signals |= _mechanical_call_signals(method.calls)
    for field in cls.field_assignments:
        signals |= _mechanical_call_signals(field.calls)
    for nested in cls.nested_classes:
        for field in nested.field_assignments:
            signals |= _mechanical_call_signals(field.calls)
    return frozenset(signals)


def _difficulty(signals: frozenset[str]) -> int:
    if not signals:
        return 0
    return min(3, max(_DIFFICULTY.get(s, 0) for s in signals))


def compute_work_list(resolved: ResolvedRepo, repo_id: str) -> list[list[MigrationUnit]]:
    model_classes = find_pydantic_model_classes(resolved)

    module_units: dict[str, MigrationUnit] = {}
    for fq, module in resolved.modules.items():
        symbols: list[SymbolRef] = []
        signals: set[str] = set()
        for cls in module.classes:
            base_kind = model_classes.get((fq, cls.name))
            cls_signals = class_signals(cls, base_kind)
            if cls_signals:
                signals |= cls_signals
                symbols.append(
                    SymbolRef(
                        repo_id=repo_id,
                        fqname=f"{fq}.{cls.name}",
                        kind=SymbolKind.CLASS,
                        path=resolved.module_paths[fq],
                        start_line=cls.start_line,
                        end_line=cls.end_line,
                    )
                )
        if signals:
            module_units[fq] = MigrationUnit(
                module=fq,
                path=resolved.module_paths[fq],
                symbols=tuple(symbols),
                signals=frozenset(signals),
                est_difficulty=_difficulty(frozenset(signals)),
            )

    edges: list[tuple[str, str]] = [(e.from_module, e.to_module) for e in resolved.import_edges]
    batches = topo_batches(set(resolved.modules), edges)

    result: list[list[MigrationUnit]] = []
    for batch in batches:
        units = [module_units[m] for m in batch if m in module_units]
        if units:
            result.append(units)
    return result


def import_edges_touching(
    resolved: ResolvedRepo, target_module: str, name: str | None = None
) -> list[ImportEdge]:
    """Convenience query used by tests and, later, by targeted-strategy retrieval in
    Phase 4 triage: "does anything import BaseSettings from pydantic"."""
    return [
        e
        for e in resolved.import_edges
        if e.to_module == target_module and (name is None or name in e.imported_names)
    ]
