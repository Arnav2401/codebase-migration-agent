"""`Field(...)` keyword argument renames (docs/phase-3-loop.md T1 table).

Split by actual risk rather than lumped as one "mechanical" bucket the way the plan's table
first sketches it — some of these kwargs renamed cleanly, one inverts a boolean's meaning:
  - regex= -> pattern=            straight rename, same semantics [mechanical]
  - min_items= -> min_length=     straight rename, same semantics [mechanical]
  - max_items= -> max_length=     straight rename, same semantics [mechanical]
  - allow_mutation=False -> frozen=True   INVERTED meaning, not a rename. Auto-rewritten
    only when the value is a literal True/False (safe to invert mechanically); flagged
    needs-review for anything else (a variable, an expression) rather than guessing.
  - const=<value>                 v2 has no direct equivalent (use Literal[<value>] as the
    type annotation instead, a type-level change this rule can't make from inside a Field()
    call) — always flagged needs-review, never rewritten.
  - unique_items=True             removed entirely in v2 with no Field-level replacement
    (use a validator or a set-like construct) — always flagged needs-review.
"""

from __future__ import annotations

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit

RULE_ID = "field_v1_kwargs"

_STRAIGHT_RENAMES = {"regex": "pattern", "min_items": "min_length", "max_items": "max_length"}
_NO_EQUIVALENT_NOTES = {
    "const": "const= has no v2 equivalent inside Field() — use Literal[...] as the type annotation",
    "unique_items": "unique_items= was removed in v2 with no Field-level replacement",
}


def _is_field_call(node: cst.Call) -> bool:
    func = node.func
    return (isinstance(func, cst.Name) and func.value == "Field") or (
        isinstance(func, cst.Attribute) and func.attr.value == "Field"
    )


class _Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        self.edits: list[RuleEdit] = []

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        if not _is_field_call(updated_node):
            return updated_node

        pos = self.get_metadata(PositionProvider, original_node)
        new_args = []
        changed = False

        for arg in updated_node.args:
            keyword = arg.keyword.value if arg.keyword is not None else None

            if keyword in _STRAIGHT_RENAMES:
                new_name = _STRAIGHT_RENAMES[keyword]
                new_args.append(arg.with_changes(keyword=cst.Name(new_name)))
                changed = True
                self.edits.append(
                    RuleEdit(RULE_ID, "", pos.start.line, f"{keyword}=...", f"{new_name}=...")
                )
                continue

            if (
                keyword == "allow_mutation"
                and isinstance(arg.value, cst.Name)
                and arg.value.value
                in (
                    "True",
                    "False",
                )
            ):
                inverted = "False" if arg.value.value == "True" else "True"
                new_args.append(
                    arg.with_changes(keyword=cst.Name("frozen"), value=cst.Name(inverted))
                )
                changed = True
                self.edits.append(
                    RuleEdit(
                        RULE_ID,
                        "",
                        pos.start.line,
                        f"allow_mutation={arg.value.value}",
                        f"frozen={inverted}",
                        note="boolean inverted: allow_mutation and frozen have opposite polarity",
                    )
                )
                continue

            if keyword == "allow_mutation":
                self.edits.append(
                    RuleEdit(
                        RULE_ID,
                        "",
                        pos.start.line,
                        "allow_mutation=<non-literal expression>",
                        "",
                        note="allow_mutation= is not a literal True/False — needs manual "
                        "inversion to frozen=, not auto-rewritten",
                    )
                )
                continue

            if keyword in _NO_EQUIVALENT_NOTES:
                self.edits.append(
                    RuleEdit(
                        RULE_ID,
                        "",
                        pos.start.line,
                        f"{keyword}=...",
                        "",
                        note=_NO_EQUIVALENT_NOTES[keyword],
                    )
                )

            new_args.append(arg)

        if not changed:
            return updated_node
        return updated_node.with_changes(args=new_args)


class _Rule:
    id = RULE_ID
    description = (
        "Field() kwarg renames: regex/min_items/max_items; flags allow_mutation/const/unique_items"
    )
    # the rewritten subset is mechanical; the unrewritten subset is flagged needs-review per-edit
    confidence: Confidence = "mechanical"

    def applies(self, tree: cst.Module) -> bool:
        return "Field(" in tree.code

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        transformer = _Transformer()
        new_tree = MetadataWrapper(tree).visit(transformer)
        return new_tree, transformer.edits


rule: CodemodRule = _Rule()
