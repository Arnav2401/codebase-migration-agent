"""Intermediate representation produced by parser.py, consumed by resolver.py and
relevance.py. Deliberately not part of pmigrate.types (docs/interfaces.md) — the IR is an
internal detail of how Phase 1 gets from source text to a graph; nothing outside `graph/`
should depend on its shape. What crosses the module boundary is SymbolRef and friends.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCall:
    """One call site, e.g. `m.dict()` or `Field(regex="...")`."""

    callee_text: str  # textual callee: "m.dict", "Field", "self.parse_obj"
    line: int  # 1-indexed
    kwargs: tuple[str, ...]  # keyword argument names used at this call site


@dataclass(frozen=True)
class ParsedAssignment:
    """A `name = ...` or `name: Type = ...` statement, at module or class-body level."""

    name: str
    line: int
    calls: tuple[ParsedCall, ...]  # calls appearing on the RHS


@dataclass(frozen=True)
class ParsedFunction:
    name: str
    decorators: tuple[str, ...]  # decorator callee names, e.g. "validator", "property"
    params: tuple[str, ...]
    start_line: int
    end_line: int
    calls: tuple[ParsedCall, ...]  # every call site anywhere in the body, regardless of nesting


@dataclass(frozen=True)
class ParsedClass:
    name: str
    bases: tuple[str, ...]  # raw base-class expressions, e.g. "BaseModel", "pydantic.BaseModel"
    decorators: tuple[str, ...]
    start_line: int
    end_line: int
    nested_classes: tuple[ParsedClass, ...]  # e.g. `class Config:` inside a model
    methods: tuple[ParsedFunction, ...]
    field_assignments: tuple[ParsedAssignment, ...]  # class-body-level `name: T = Field(...)`


@dataclass(frozen=True)
class ImportedName:
    """One binding introduced by an import statement.

    Unifies `import a.b.c [as d]` and `from x import y [as z]` so resolver.py has a single
    shape to resolve: for `kind="import"`, `module_path` IS the thing being imported and
    `original_name` is None; for `kind="from"`, `module_path` is what comes after `from`
    (already join with the relative prefix's target, if any) and `original_name` is the
    attribute pulled from it.
    """

    kind: str  # "import" | "from"
    module_path: str  # dotted text; "" for a bare `from . import x`
    level: int  # 0 = absolute; N = N leading dots (only meaningful for kind="from")
    original_name: str | None  # the name after `import` in a `from` statement; "*" for star
    imported_as: str  # local binding name (alias, or original_name/module_path if unaliased)
    type_only: bool  # True if nested inside `if TYPE_CHECKING:`
    line: int


@dataclass(frozen=True)
class ParsedModule:
    path: str  # repo-relative path, e.g. "app/models/user.py"
    imports: tuple[ImportedName, ...]
    classes: tuple[ParsedClass, ...]  # module-level classes only
    functions: tuple[ParsedFunction, ...]  # module-level functions only
    assignments: tuple[ParsedAssignment, ...]  # module-level assignments only
    has_syntax_errors: bool  # tree-sitter is error-tolerant; this flags a partial parse
