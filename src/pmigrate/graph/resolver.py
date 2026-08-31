"""Phase 1 step 1.2 (docs/phase-1-graph.md) — turn ImportedName records into module-level
edges between real modules. This is called out in the plan as "the hard part" and "where
correctness is won or lost" — write it test-first, which is why every branch here has a
matching case in tests/graph/fixtures/sample_repo (see test_resolver.py).

What this handles (docs/phase-1-graph.md 1.2):
  - relative imports at any depth, including `from . import x` with no dotted suffix
  - src/ layout detection (a repo where the real package root is under src/)
  - `__init__.py` re-exports: `from app.models import User` where `models/__init__.py`
    does `from .user import User` — resolved through to the ultimate defining module
  - aliasing (doesn't affect module-level edges, which are about modules not names)
  - star imports — recorded as an edge with original_name="*", individual names unresolved
  - TYPE_CHECKING-guarded imports — kept, edge carries type_only=True
  - third-party vs first-party — an edge whose target isn't in this repo's module set is
    marked is_first_party=False; the module dotted name is still recorded so a query like
    "does anything import BaseSettings from pydantic" is answerable without cloning pydantic

What this does NOT handle (docs/phase-1-graph.md "Pitfalls" — measure it, don't chase it):
  - PEP 420 implicit namespace packages spanning multiple search roots
  - imports resolved dynamically (importlib, sys.path manipulation, plugin registries)
  - re-export chains longer than REEXPORT_MAX_HOPS (cycle/pathological-depth guard)
resolve_repo() reports `unresolved_count` / `total_import_count` precisely so resolution
coverage is a measured number (docs/phase-1-graph.md acceptance criteria: >=90%), not a
claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from pmigrate.graph.ir import ImportedName, ParsedModule
from pmigrate.graph.parser import parse_file

REEXPORT_MAX_HOPS = 5


@dataclass(frozen=True)
class ImportEdge:
    from_module: str
    to_module: str  # resolved dotted module path (first-party fqname, or third-party dotted name)
    imported_names: tuple[str, ...]  # original names pulled from to_module; ("*",) for star
    is_first_party: bool
    type_only: bool
    line: int


@dataclass(frozen=True)
class ResolvedRepo:
    modules: dict[str, ParsedModule]  # fqname -> parsed module, first-party only
    module_paths: dict[str, str]  # fqname -> repo-relative path
    import_edges: tuple[ImportEdge, ...]
    unresolved_count: int
    total_import_count: int

    @property
    def resolution_coverage(self) -> float:
        if self.total_import_count == 0:
            return 1.0
        return 1 - (self.unresolved_count / self.total_import_count)


def _source_root(paths: list[str]) -> str:
    """Detect a src/ layout: if every first-party .py file lives under a top-level src/
    directory, that prefix is stripped when computing dotted module names."""
    if paths and all(p == "src" or p.startswith("src/") for p in paths):
        return "src/"
    return ""


def _path_to_fqname(path: str, source_root: str) -> str:
    relative = path[len(source_root) :] if source_root and path.startswith(source_root) else path
    if relative.endswith("/__init__.py"):
        relative = relative[: -len("/__init__.py")]
    elif relative == "__init__.py":
        relative = ""
    elif relative.endswith(".py"):
        relative = relative[: -len(".py")]
    return relative.replace("/", ".")


def _is_package(fqname: str, module_paths: dict[str, str]) -> bool:
    path = module_paths.get(fqname, "")
    return path.endswith("__init__.py")


def _package_of(fqname: str, module_paths: dict[str, str]) -> str:
    if _is_package(fqname, module_paths):
        return fqname
    return fqname.rsplit(".", 1)[0] if "." in fqname else ""


def _relative_anchor(importing_fqname: str, level: int, module_paths: dict[str, str]) -> str | None:
    """Resolve the `level` leading dots of a relative import to an absolute package
    prefix, anchored at the importing module's own package (Python's actual semantics —
    level=1 means "this package", not "this module's directory")."""
    package = _package_of(importing_fqname, module_paths)
    parts = package.split(".") if package else []
    climb = level - 1
    if climb > len(parts):
        return None  # climbed above the repo root — unresolvable
    if climb > 0:
        parts = parts[:-climb]
    return ".".join(parts)


def _is_first_party(name: str, modules: dict[str, ParsedModule]) -> bool:
    if name in modules:
        return True
    return any(m == name or m.startswith(name + ".") for m in modules)


def _follow_reexport(
    module_fqname: str, name: str, modules: dict[str, ParsedModule], hops: int = 0
) -> str:
    """If `name` in `module_fqname` is itself just an import binding (a re-export, the
    classic `app/models/__init__.py: from .user import User` pattern), chase it to the
    module that actually defines it. Bounded depth guards against import cycles."""
    if hops >= REEXPORT_MAX_HOPS:
        return module_fqname
    module = modules.get(module_fqname)
    if module is None:
        return module_fqname
    for imp in module.imports:
        if imp.imported_as != name or imp.original_name == "*":
            continue
        target = _resolve_from_target(module_fqname, imp.module_path, imp.level, modules)
        if target is None or target == module_fqname:
            return module_fqname
        next_name = imp.original_name or name
        if target in modules and any(i.imported_as == next_name for i in modules[target].imports):
            return _follow_reexport(target, next_name, modules, hops + 1)
        return target
    return module_fqname  # `name` is defined directly in this module, not re-exported


def _resolve_from_target(
    importing_fqname: str, module_path: str, level: int, modules: dict[str, ParsedModule]
) -> str | None:
    if level == 0:
        return module_path
    anchor = _relative_anchor(importing_fqname, level, modules_to_paths(modules))
    if anchor is None:
        return None
    return f"{anchor}.{module_path}" if module_path else anchor


def resolve_import_target(
    importing_fqname: str, imp: ImportedName, modules: dict[str, ParsedModule]
) -> str | None:
    """Public seam onto the same module-target resolution resolve_repo() uses internally,
    for callers (relevance.py) that need to answer "what module does this specific import
    binding point at" without redoing resolve_repo()'s whole-repo edge-building pass."""
    return _resolve_from_target(importing_fqname, imp.module_path, imp.level, modules)


def modules_to_paths(modules: dict[str, ParsedModule]) -> dict[str, str]:
    return {fq: m.path for fq, m in modules.items()}


def resolve_repo(files: dict[str, bytes]) -> ResolvedRepo:
    """files: repo-relative path -> source bytes, for every first-party .py file."""
    paths = sorted(files)
    root = _source_root(paths)

    modules: dict[str, ParsedModule] = {}
    module_paths: dict[str, str] = {}
    for path in paths:
        fqname = _path_to_fqname(path, root)
        if fqname == "":
            continue  # top-level src/__init__.py with nothing to name it; vanishingly rare
        modules[fqname] = parse_file(path, files[path])
        module_paths[fqname] = path

    edges: list[ImportEdge] = []
    unresolved = 0
    total = 0

    for fqname, module in modules.items():
        for imp in module.imports:
            total += 1
            target = _resolve_from_target(fqname, imp.module_path, imp.level, modules)
            if target is None:
                unresolved += 1
                continue

            is_first_party = _is_first_party(target, modules)
            name = imp.original_name

            if is_first_party and name is not None and name != "*":
                # follow submodule-vs-reexport: prefer an actual submodule if one exists
                submodule = f"{target}.{name}"
                if submodule in modules:
                    target = submodule
                elif target in modules:
                    target = _follow_reexport(target, name, modules)

            edges.append(
                ImportEdge(
                    from_module=fqname,
                    to_module=target,
                    imported_names=(name,) if name else (),
                    is_first_party=_is_first_party(target, modules),
                    type_only=imp.type_only,
                    line=imp.line,
                )
            )

    return ResolvedRepo(
        modules=modules,
        module_paths=module_paths,
        import_edges=tuple(edges),
        unresolved_count=unresolved,
        total_import_count=total,
    )
