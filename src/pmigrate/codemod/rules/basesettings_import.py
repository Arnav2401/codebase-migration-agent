"""`BaseSettings` moved from `pydantic` to `pydantic_settings` in v2 (docs/phase-3-loop.md
T1 table). Handles BOTH real-world spellings of "using BaseSettings" — found the hard way
that only handling one was not enough:

  1. `from pydantic import BaseSettings` -> `from pydantic_settings import BaseSettings`
     (splitting one import line into two when BaseSettings is imported alongside other
     names needs LibCST's FlattenSentinel, verified interactively before writing this).
  2. `import pydantic` + qualified `pydantic.BaseSettings` usage elsewhere in the file —
     a DIFFERENT syntactic shape that the first pattern's ImportFrom-only transformer
     silently did nothing for. Found against a real corpus repo
     (`madkote/fastapi-plugins`, `class PluginSettings(pydantic.BaseSettings):`), not a
     synthetic fixture: the very first real end-to-end run applied this rule, reported
     success, and the exact same `PydanticImportError: BaseSettings has been moved...`
     was still there afterward — the codemod had done nothing for the pattern this repo
     actually used. Fixed by also rewriting `pydantic.BaseSettings` attribute access to
     `pydantic_settings.BaseSettings` and inserting `import pydantic_settings` (after the
     last existing top-level import, and only when a qualified rewrite actually happened)
     — the original `import pydantic` statement is left alone, since the module is almost
     always still used for other things.

Deliberately does NOT add `pydantic-settings` to any dependency file — that's a real
external action (adding a package requirement) that belongs to whatever applies the diff
and knows the project's dependency-management convention (requirements.txt vs pyproject.toml
vs poetry), not to a codemod rule operating on one Python file in isolation.
"""

from __future__ import annotations

import libcst as cst
from libcst import FlattenSentinel
from libcst.metadata import MetadataWrapper, PositionProvider

from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit

RULE_ID = "basesettings_import_to_pydantic_settings"


class _Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.edits: list[RuleEdit] = []
        self._needs_pydantic_settings_import = False

    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine | FlattenSentinel[cst.BaseStatement]:
        if len(updated_node.body) != 1 or not isinstance(updated_node.body[0], cst.ImportFrom):
            return updated_node

        imp = updated_node.body[0]
        if not (isinstance(imp.module, cst.Name) and imp.module.value == "pydantic"):
            return updated_node
        if isinstance(imp.names, cst.ImportStar):
            return updated_node

        has_base_settings = any(n.name.value == "BaseSettings" for n in imp.names)
        if not has_base_settings:
            return updated_node

        pos = self.get_metadata(PositionProvider, original_node)
        self.edits.append(
            RuleEdit(
                rule_id=RULE_ID,
                path="",
                line=pos.start.line,
                before="from pydantic import ... BaseSettings ...",
                after="from pydantic_settings import BaseSettings",
            )
        )

        remaining = [n for n in imp.names if n.name.value != "BaseSettings"]
        new_statements: list[cst.BaseStatement] = []
        if remaining:
            fixed = [n.with_changes(comma=cst.MaybeSentinel.DEFAULT) for n in remaining]
            new_statements.append(updated_node.with_changes(body=[imp.with_changes(names=fixed)]))

        new_statements.append(
            cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=cst.Name("pydantic_settings"),
                        names=[cst.ImportAlias(name=cst.Name("BaseSettings"))],
                    )
                ]
            )
        )
        return FlattenSentinel(new_statements)

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        if not (
            isinstance(updated_node.value, cst.Name)
            and updated_node.value.value == "pydantic"
            and updated_node.attr.value == "BaseSettings"
        ):
            return updated_node
        pos = self.get_metadata(PositionProvider, original_node)
        self.edits.append(
            RuleEdit(
                rule_id=RULE_ID,
                path="",
                line=pos.start.line,
                before="pydantic.BaseSettings",
                after="pydantic_settings.BaseSettings",
            )
        )
        self._needs_pydantic_settings_import = True
        return updated_node.with_changes(value=cst.Name("pydantic_settings"))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if not self._needs_pydantic_settings_import:
            return updated_node
        new_import = cst.SimpleStatementLine(
            body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("pydantic_settings"))])]
        )
        body = list(updated_node.body)
        insert_at = 0
        for i, stmt in enumerate(body):
            if isinstance(stmt, cst.SimpleStatementLine) and any(
                isinstance(s, cst.Import | cst.ImportFrom) for s in stmt.body
            ):
                insert_at = i + 1
        body.insert(insert_at, new_import)
        return updated_node.with_changes(body=body)


class _Rule:
    id = RULE_ID
    description = (
        "BaseSettings -> pydantic_settings (both `from pydantic import` and `pydantic.` forms)"
    )
    confidence: Confidence = "mechanical"

    def applies(self, tree: cst.Module) -> bool:
        return "BaseSettings" in tree.code and "pydantic" in tree.code

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        transformer = _Transformer()
        new_tree = MetadataWrapper(tree).visit(transformer)
        return new_tree, transformer.edits


rule: CodemodRule = _Rule()
