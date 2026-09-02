"""`@validator('x')` -> `@field_validator('x')` + `@classmethod` (docs/phase-3-loop.md T1
table). "likely" not "mechanical": the `values` parameter v1 passed to a multi-field
validator becomes `info.data` in v2 — a real signature/body change this rule does not
attempt, since it requires understanding the function body, not just the decorator. The
decorator and the missing `@classmethod` are rewritten; a body that references `values`
will fail at test time and needs a human or T2 pass, not this rule pretending otherwise.
"""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit

RULE_ID = "validator_to_field_validator"


def _decorator_callee_name(decorator: cst.Decorator) -> str | None:
    expr = decorator.decorator
    if isinstance(expr, cst.Call) and isinstance(expr.func, cst.Name):
        return expr.func.value
    if isinstance(expr, cst.Name):
        return expr.value
    return None


class _Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.edits: list[RuleEdit] = []

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        names = [_decorator_callee_name(d) for d in updated_node.decorators]
        if "validator" not in names:
            return updated_node

        pos = self.get_metadata(PositionProvider, original_node)
        new_decorators = []
        rewrote_any = False
        for decorator, name in zip(updated_node.decorators, names, strict=True):
            expr = decorator.decorator
            if name == "validator" and isinstance(expr, cst.Call):
                new_decorators.append(
                    decorator.with_changes(
                        decorator=expr.with_changes(func=cst.Name("field_validator"))
                    )
                )
                rewrote_any = True
            else:
                # `@validator` used bare (no call) is never valid pydantic v1 usage —
                # pydantic's real `@validator` always takes at least one field-name arg.
                # Found live against a real corpus repo (docs/decisions.md D22):
                # `plugboard-schemas` imports its OWN unrelated decorator named
                # `validator` (`from ._validator_registry import validator`), and this
                # rule's name-only matching (no import-provenance check) collided with it.
                # Leaving it untouched — rather than asserting it must be a Call and
                # crashing — is the correct behavior for a name that isn't actually
                # pydantic's validator, and is also the safe default if it somehow were.
                new_decorators.append(decorator)

        if not rewrote_any:
            return updated_node

        if "classmethod" not in names:
            new_decorators.append(cst.Decorator(decorator=cst.Name("classmethod")))
            added_classmethod_note = " (added missing @classmethod)"
        else:
            added_classmethod_note = ""

        self.edits.append(
            RuleEdit(
                rule_id=RULE_ID,
                path="",
                line=pos.start.line,
                before="@validator(...)",
                after=f"@field_validator(...){added_classmethod_note}",
                note="check the function body for a `values` parameter — that becomes "
                "`info.data` in v2 and is not rewritten by this rule",
            )
        )
        return updated_node.with_changes(decorators=new_decorators)


class _Rule:
    id = RULE_ID
    description = "@validator -> @field_validator + @classmethod"
    confidence: Confidence = "likely"

    def applies(self, tree: cst.Module) -> bool:
        return "@validator" in tree.code or "validator(" in tree.code

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        transformer = _Transformer()
        new_tree = MetadataWrapper(tree).visit(transformer)
        return new_tree, transformer.edits


rule: CodemodRule = _Rule()
