"""Nested `class Config: ...` -> `model_config = ConfigDict(...)` (docs/phase-3-loop.md T1
table). The structurally hairiest T1 rule: it removes a nested ClassDef statement and
replaces it with a class-level assignment, verified interactively (LibCST node shapes for
statement replacement, and the AssignEqual whitespace needed to avoid `key = value` instead
of the conventional `key=value`) before writing this.

Key-rename table is intentionally conservative. Known-safe renames get rewritten; anything
outside the table is KEPT in the new ConfigDict call under its original key (never silently
dropped — a dropped setting is a silent behavior change) but flagged needs-review, since an
unrecognized key might not even be valid in ConfigDict at all.
`json_encoders` is deliberately excluded from this table even though it's a known v1 key —
docs/phase-3-loop.md lists it as its own needs-review case (Field-level serializers are a
real redesign, not a kwarg rename), so it's left in the table as a flagged pass-through
rather than silently rewritten here.

Ensures `ConfigDict` is actually importable wherever it generates a reference to it — found
missing against a real corpus repo (`madkote/fastapi-plugins`): the rewrite produced
`model_config = ConfigDict(...)` correctly, but nothing in the file imported `ConfigDict`,
so the "fix" traded one error (`PydanticImportError`) for another (`NameError: name
'ConfigDict' is not defined`) the first real end-to-end run actually hit. Same shape of gap
as `basesettings_import.py`'s qualified-attribute miss — a rewrite that's syntactically
present but doesn't ensure its own name resolves. Adds `ConfigDict` to an existing
`from pydantic import ...` line when one exists, or inserts a new
`from pydantic import ConfigDict` after the last top-level import otherwise.
"""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit

RULE_ID = "config_class_to_configdict"

_NO_EQUAL_SPACE = cst.AssignEqual(
    whitespace_before=cst.SimpleWhitespace(""), whitespace_after=cst.SimpleWhitespace("")
)

_STRAIGHT_RENAMES = {
    "orm_mode": "from_attributes",
    "anystr_strip_whitespace": "str_strip_whitespace",
}
_SAME_NAME_KEEP = {"extra", "arbitrary_types_allowed", "validate_assignment", "populate_by_name"}
_INVERTED_BOOLEAN = {"allow_mutation": "frozen"}


def _config_class(class_body: cst.BaseSuite) -> cst.ClassDef | None:
    # a one-line class suite (`class X: pass`) can't contain a nested class at all —
    # BaseSuite covers that case too, IndentedBlock is the only variant worth walking.
    if not isinstance(class_body, cst.IndentedBlock):
        return None
    for stmt in class_body.body:
        if isinstance(stmt, cst.ClassDef) and stmt.name.value == "Config":
            return stmt
    return None


def _config_assignments(config_class: cst.ClassDef) -> list[tuple[str, cst.BaseExpression]]:
    assignments = []
    for stmt in config_class.body.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.Assign) and len(small.targets) == 1:
                target = small.targets[0].target
                if isinstance(target, cst.Name):
                    assignments.append((target.value, small.value))
    return assignments


class _Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.edits: list[RuleEdit] = []
        self._needs_configdict_import = False

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        config_class = _config_class(updated_node.body)
        if config_class is None:
            return updated_node

        assignments = _config_assignments(config_class)
        # Position metadata is keyed by node identity in the ORIGINAL tree PositionProvider
        # indexed — `config_class` came from `updated_node.body`, which bottom-up traversal
        # may have already re-wrapped into a fresh object even with no real change beneath
        # it, so look up the outer (original_node) class's position instead; found via
        # a live KeyError, not anticipated in advance.
        pos = self.get_metadata(PositionProvider, original_node)
        new_args = []
        needs_review_keys = []

        for key, value in assignments:
            if key in _STRAIGHT_RENAMES:
                new_args.append(
                    cst.Arg(
                        keyword=cst.Name(_STRAIGHT_RENAMES[key]), value=value, equal=_NO_EQUAL_SPACE
                    )
                )
            elif key in _SAME_NAME_KEEP:
                new_args.append(cst.Arg(keyword=cst.Name(key), value=value, equal=_NO_EQUAL_SPACE))
            elif (
                key in _INVERTED_BOOLEAN
                and isinstance(value, cst.Name)
                and value.value in ("True", "False")
            ):
                inverted = "False" if value.value == "True" else "True"
                new_args.append(
                    cst.Arg(
                        keyword=cst.Name(_INVERTED_BOOLEAN[key]),
                        value=cst.Name(inverted),
                        equal=_NO_EQUAL_SPACE,
                    )
                )
            else:
                # unknown, or an inverted-boolean key with a non-literal value we won't
                # guess at — keep the original key verbatim rather than drop it silently
                new_args.append(cst.Arg(keyword=cst.Name(key), value=value, equal=_NO_EQUAL_SPACE))
                needs_review_keys.append(key)

        new_call = cst.Call(func=cst.Name("ConfigDict"), args=new_args)
        new_assign_stmt = cst.SimpleStatementLine(
            body=[cst.Assign(targets=[cst.AssignTarget(cst.Name("model_config"))], value=new_call)],
            leading_lines=config_class.leading_lines,
        )

        new_body = [s for s in updated_node.body.body if s is not config_class]
        # insert the new assignment where Config used to be, preserving relative order
        original_index = list(updated_node.body.body).index(config_class)
        new_body = list(updated_node.body.body)
        new_body[original_index] = new_assign_stmt

        note = (
            f"unrecognized Config key(s) kept as-is, verify: {', '.join(needs_review_keys)}"
            if needs_review_keys
            else None
        )
        self.edits.append(
            RuleEdit(
                rule_id=RULE_ID,
                path="",
                line=pos.start.line,
                before="class Config: ...",
                after="model_config = ConfigDict(...)",
                note=note,
            )
        )

        self._needs_configdict_import = True
        return updated_node.with_changes(body=updated_node.body.with_changes(body=new_body))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if not self._needs_configdict_import:
            return updated_node

        body = list(updated_node.body)
        last_import_index = -1
        for i, stmt in enumerate(body):
            if not isinstance(stmt, cst.SimpleStatementLine):
                continue
            for small in stmt.body:
                if isinstance(small, cst.Import | cst.ImportFrom):
                    last_import_index = i
                # already importable — nothing to do
                if (
                    isinstance(small, cst.ImportFrom)
                    and isinstance(small.module, cst.Name)
                    and small.module.value == "pydantic"
                    and not isinstance(small.names, cst.ImportStar)
                    and any(n.name.value == "ConfigDict" for n in small.names)
                ):
                    return updated_node

        # prefer extending an existing `from pydantic import ...` line over adding a new
        # statement, matching how a human would actually write this
        for i, stmt in enumerate(body):
            if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
                continue
            imp = stmt.body[0]
            if (
                isinstance(imp, cst.ImportFrom)
                and isinstance(imp.module, cst.Name)
                and imp.module.value == "pydantic"
                and not isinstance(imp.names, cst.ImportStar)
            ):
                comma = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
                fixed_names = [n.with_changes(comma=comma) for n in imp.names]
                new_names = [*fixed_names, cst.ImportAlias(name=cst.Name("ConfigDict"))]
                body[i] = stmt.with_changes(body=[imp.with_changes(names=new_names)])
                return updated_node.with_changes(body=body)

        new_import = cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=cst.Name("pydantic"),
                    names=[cst.ImportAlias(name=cst.Name("ConfigDict"))],
                )
            ]
        )
        body.insert(last_import_index + 1, new_import)
        return updated_node.with_changes(body=body)


class _Rule:
    id = RULE_ID
    description = "nested class Config -> model_config = ConfigDict(...)"
    confidence: Confidence = "mechanical"

    def applies(self, tree: cst.Module) -> bool:
        return "class Config" in tree.code

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        transformer = _Transformer()
        new_tree = MetadataWrapper(tree).visit(transformer)
        return new_tree, transformer.edits


rule: CodemodRule = _Rule()
