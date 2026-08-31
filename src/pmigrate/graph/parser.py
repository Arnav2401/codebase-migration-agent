"""Phase 1 step 1.1 (docs/phase-1-graph.md) — tree-sitter extraction of one Python source
file into a ParsedModule.

Deliberately narrow: this module knows nothing about the repo it lives in (no fqname
computation, no cross-file resolution) — that is resolver.py's job, which needs whole-repo
context this module doesn't have. `parse_file` is a pure function: bytes in, IR out. Node
shapes below were confirmed interactively against tree-sitter-python before writing this,
not guessed from memory of the grammar.

Deliberate scope cuts (see docs/phase-1-graph.md "Pitfalls" — dynamic Python is
unresolvable, and the right response is to measure that, not chase it):
  - module docstrings are not extracted — nothing downstream consumes them.
  - a decorator's own arguments are not parsed beyond its callee name (`@validator("x")`
    is recorded as decorator "validator"; which fields it applies to is validation-time
    semantics the graph doesn't need to place an edge).
  - only import/class/function/assignment statements are collected while walking a block;
    plain expression statements, `pass`, bare docstrings, etc. are silently skipped.
  - if/elif/else and try/except ARE walked at every nesting depth (so a TYPE_CHECKING
    guard or a try/except ImportError fallback is still seen) — the cut is in which
    statement *kinds* are collected, not how deep the walk goes.
"""

from __future__ import annotations

import tree_sitter
import tree_sitter_python as tspython

from pmigrate.graph.ir import (
    ImportedName,
    ParsedAssignment,
    ParsedCall,
    ParsedClass,
    ParsedFunction,
    ParsedModule,
)

_LANGUAGE = tree_sitter.Language(tspython.language())


def _text(node: tree_sitter.Node | None, source: bytes) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _body_block(node: tree_sitter.Node) -> tree_sitter.Node | None:
    """The `block` child of a construct whose body we don't need a field name for
    (try/except/elif/else all nest their body as a plain `block` child)."""
    for child in node.children:
        if child.type == "block":
            return child
    return None


def parse_file(path: str, source: bytes) -> ParsedModule:
    tree = tree_sitter.Parser(_LANGUAGE).parse(source)
    root = tree.root_node

    imports: list[ImportedName] = []
    classes: list[ParsedClass] = []
    functions: list[ParsedFunction] = []
    assignments: list[ParsedAssignment] = []

    _walk_block(root, source, imports, classes, functions, assignments, type_only=False)

    return ParsedModule(
        path=path,
        imports=tuple(imports),
        classes=tuple(classes),
        functions=tuple(functions),
        assignments=tuple(assignments),
        has_syntax_errors=root.has_error,
    )


def _walk_block(
    block: tree_sitter.Node,
    source: bytes,
    imports: list[ImportedName],
    classes: list[ParsedClass],
    functions: list[ParsedFunction],
    assignments: list[ParsedAssignment],
    type_only: bool,
) -> None:
    for child in block.children:
        t = child.type

        if t == "import_statement":
            imports.extend(_extract_import_statement(child, source, type_only))
        elif t == "import_from_statement":
            imports.extend(_extract_import_from_statement(child, source, type_only))
        elif t == "if_statement":
            _walk_if(child, source, imports, classes, functions, assignments, type_only)
        elif t == "try_statement":
            _walk_try(child, source, imports, classes, functions, assignments, type_only)
        elif t == "decorated_definition":
            decorators = _decorator_names(child, source)
            inner = child.children[-1]
            if inner.type == "function_definition":
                functions.append(_extract_function(inner, source, decorators))
            elif inner.type == "class_definition":
                classes.append(_extract_class(inner, source, decorators))
        elif t == "function_definition":
            functions.append(_extract_function(child, source, ()))
        elif t == "class_definition":
            classes.append(_extract_class(child, source, ()))
        elif (
            t == "expression_statement"
            and child.children
            and child.children[0].type == "assignment"
        ):
            assignments.append(_extract_assignment(child.children[0], source))


def _walk_if(
    node: tree_sitter.Node,
    source: bytes,
    imports: list[ImportedName],
    classes: list[ParsedClass],
    functions: list[ParsedFunction],
    assignments: list[ParsedAssignment],
    type_only: bool,
) -> None:
    condition = _text(node.child_by_field_name("condition"), source)
    branch_type_only = type_only or "TYPE_CHECKING" in condition

    consequence = node.child_by_field_name("consequence")
    if consequence is not None:
        _walk_block(consequence, source, imports, classes, functions, assignments, branch_type_only)

    for child in node.children:
        if child.type == "elif_clause":
            # elif conditions don't inherit the `if`'s TYPE_CHECKING-ness — evaluate fresh,
            # matching how `if TYPE_CHECKING: ... elif OTHER: ...` actually behaves.
            _walk_if(child, source, imports, classes, functions, assignments, type_only)
        elif child.type == "else_clause":
            body = _body_block(child)
            if body is not None:
                _walk_block(body, source, imports, classes, functions, assignments, type_only)


def _walk_try(
    node: tree_sitter.Node,
    source: bytes,
    imports: list[ImportedName],
    classes: list[ParsedClass],
    functions: list[ParsedFunction],
    assignments: list[ParsedAssignment],
    type_only: bool,
) -> None:
    for child in node.children:
        if child.type == "block":
            _walk_block(child, source, imports, classes, functions, assignments, type_only)
        elif child.type in ("except_clause", "else_clause", "finally_clause"):
            body = _body_block(child)
            if body is not None:
                _walk_block(body, source, imports, classes, functions, assignments, type_only)


def _decorator_names(decorated_def: tree_sitter.Node, source: bytes) -> tuple[str, ...]:
    names = []
    for child in decorated_def.children:
        if child.type != "decorator":
            continue
        # decorator's children are ["@", <expr>] where <expr> is identifier/attribute/call
        expr = child.children[-1]
        if expr.type == "call":
            names.append(_text(expr.child_by_field_name("function"), source))
        else:
            names.append(_text(expr, source))
    return tuple(names)


def _scan_calls(node: tree_sitter.Node, source: bytes) -> list[ParsedCall]:
    calls: list[ParsedCall] = []
    if node.type == "call":
        callee = _text(node.child_by_field_name("function"), source)
        kwargs = []
        args = node.child_by_field_name("arguments")
        if args is not None:
            for arg in args.children:
                if arg.type == "keyword_argument":
                    kwargs.append(_text(arg.child_by_field_name("name"), source))
        calls.append(
            ParsedCall(callee_text=callee, line=node.start_point[0] + 1, kwargs=tuple(kwargs))
        )
    for child in node.children:
        calls.extend(_scan_calls(child, source))
    return calls


def _extract_param_names(parameters: tree_sitter.Node | None, source: bytes) -> tuple[str, ...]:
    if parameters is None:
        return ()
    names = []
    for child in parameters.children:
        if child.type in ("identifier",):
            names.append(_text(child, source))
        elif child.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            name_node = child.child_by_field_name("name") or (
                child.children[0] if child.children else None
            )
            if name_node is not None:
                names.append(_text(name_node, source))
    return tuple(names)


def _extract_function(
    node: tree_sitter.Node, source: bytes, decorators: tuple[str, ...]
) -> ParsedFunction:
    body = node.child_by_field_name("body")
    calls = _scan_calls(body, source) if body is not None else []
    return ParsedFunction(
        name=_text(node.child_by_field_name("name"), source),
        decorators=decorators,
        params=_extract_param_names(node.child_by_field_name("parameters"), source),
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        calls=tuple(calls),
    )


def _extract_assignment(node: tree_sitter.Node, source: bytes) -> ParsedAssignment:
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    calls = _scan_calls(right, source) if right is not None else []
    return ParsedAssignment(
        name=_text(left, source), line=node.start_point[0] + 1, calls=tuple(calls)
    )


def _extract_class(
    node: tree_sitter.Node, source: bytes, decorators: tuple[str, ...]
) -> ParsedClass:
    bases = []
    superclasses = node.child_by_field_name("superclasses")
    if superclasses is not None:
        for child in superclasses.children:
            if child.type in ("identifier", "attribute"):
                bases.append(_text(child, source))

    nested_classes: list[ParsedClass] = []
    methods: list[ParsedFunction] = []
    field_assignments: list[ParsedAssignment] = []

    body = node.child_by_field_name("body")
    if body is not None:
        for child in body.children:
            if child.type == "decorated_definition":
                inner_decorators = _decorator_names(child, source)
                inner = child.children[-1]
                if inner.type == "function_definition":
                    methods.append(_extract_function(inner, source, inner_decorators))
                elif inner.type == "class_definition":
                    nested_classes.append(_extract_class(inner, source, inner_decorators))
            elif child.type == "function_definition":
                methods.append(_extract_function(child, source, ()))
            elif child.type == "class_definition":
                nested_classes.append(_extract_class(child, source, ()))
            elif child.type == "expression_statement":
                if child.children and child.children[0].type == "assignment":
                    field_assignments.append(_extract_assignment(child.children[0], source))

    return ParsedClass(
        name=_text(node.child_by_field_name("name"), source),
        bases=tuple(bases),
        decorators=decorators,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        nested_classes=tuple(nested_classes),
        methods=tuple(methods),
        field_assignments=tuple(field_assignments),
    )


def _extract_import_statement(
    node: tree_sitter.Node, source: bytes, type_only: bool
) -> list[ImportedName]:
    """`import a.b.c[, d.e][ as f]` — one ImportedName per comma-separated target."""
    results = []
    line = node.start_point[0] + 1
    for child in node.children:
        if child.type == "dotted_name":
            text = _text(child, source)
            results.append(
                ImportedName(
                    kind="import",
                    module_path=text,
                    level=0,
                    original_name=None,
                    imported_as=text.split(".")[0],
                    type_only=type_only,
                    line=line,
                )
            )
        elif child.type == "aliased_import":
            name_text = _text(child.child_by_field_name("name"), source)
            alias_text = _text(child.child_by_field_name("alias"), source)
            results.append(
                ImportedName(
                    kind="import",
                    module_path=name_text,
                    level=0,
                    original_name=None,
                    imported_as=alias_text,
                    type_only=type_only,
                    line=line,
                )
            )
    return results


def _extract_import_from_statement(
    node: tree_sitter.Node, source: bytes, type_only: bool
) -> list[ImportedName]:
    """`from [.]*x.y import a[, b as c][, *]`."""
    module_node = node.child_by_field_name("module_name")
    line = node.start_point[0] + 1
    level = 0
    module_path = ""

    if module_node is not None:
        if module_node.type == "relative_import":
            for child in module_node.children:
                if child.type == "import_prefix":
                    level = len(_text(child, source))
                elif child.type == "dotted_name":
                    module_path = _text(child, source)
        else:
            module_path = _text(module_node, source)

    results = []
    for child in node.children:
        if child.type == "dotted_name" and child != module_node:
            text = _text(child, source)
            results.append(
                ImportedName(
                    kind="from",
                    module_path=module_path,
                    level=level,
                    original_name=text,
                    imported_as=text,
                    type_only=type_only,
                    line=line,
                )
            )
        elif child.type == "aliased_import":
            name_text = _text(child.child_by_field_name("name"), source)
            alias_text = _text(child.child_by_field_name("alias"), source)
            results.append(
                ImportedName(
                    kind="from",
                    module_path=module_path,
                    level=level,
                    original_name=name_text,
                    imported_as=alias_text,
                    type_only=type_only,
                    line=line,
                )
            )
        elif child.type == "wildcard_import":
            results.append(
                ImportedName(
                    kind="from",
                    module_path=module_path,
                    level=level,
                    original_name="*",
                    imported_as="*",
                    type_only=type_only,
                    line=line,
                )
            )
    return results
