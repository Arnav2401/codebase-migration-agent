"""Shared transformer building blocks used by the rule files in this package. Not itself a
rule — `rules/__init__.py`'s ALL_RULES list is what's public. Kept here rather than in
engine.py because these are codemod-specific CST patterns, not orchestration logic.
"""

from __future__ import annotations

import libcst as cst
import libcst.matchers as m
from libcst.metadata import MetadataWrapper, PositionProvider

from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit


class _CallRenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, rule_id: str, old_name: str, new_name: str) -> None:
        self.rule_id = rule_id
        self.old_name = old_name
        self.new_name = new_name
        self.edits: list[RuleEdit] = []

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        func = updated_node.func
        if not (isinstance(func, cst.Attribute) and func.attr.value == self.old_name):
            return updated_node
        new_node = updated_node.with_changes(func=func.with_changes(attr=cst.Name(self.new_name)))
        pos = self.get_metadata(PositionProvider, original_node)
        self.edits.append(
            RuleEdit(
                rule_id=self.rule_id,
                path="",
                line=pos.start.line,
                before=f"...{self.old_name}(...)",
                after=f"...{self.new_name}(...)",
            )
        )
        return new_node


def make_call_rename_rule(
    rule_id: str, description: str, confidence: Confidence, old_name: str, new_name: str
) -> CodemodRule:
    """A rename applied to any `<expr>.old_name(...)` call, regardless of what `<expr>` is
    — see protocol.py's module docstring for why that's a deliberate, not sloppy, choice."""

    pattern = m.Call(func=m.Attribute(attr=m.Name(value=old_name)))

    class _Rule:
        # Attributes are set in __init__, not as class-body statements: a class body's
        # plain statements resolve names via LOAD_NAME (class-local, then module globals)
        # — they do NOT see the enclosing factory function's locals the way a nested
        # `def` (which is what __init__ is) closes over them. `description = description`
        # directly in the class body raises NameError at runtime; found by running the
        # tests, not by reasoning about it in advance. As a bonus, __init__ assignment is
        # also what lets mypy verify Protocol conformance here at all.
        def __init__(self) -> None:
            self.id = rule_id
            self.description = description
            self.confidence = confidence

        def applies(self, tree: cst.Module) -> bool:
            return bool(m.findall(tree, pattern))

        def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
            transformer = _CallRenameTransformer(rule_id, old_name, new_name)
            new_tree = MetadataWrapper(tree).visit(transformer)
            return new_tree, transformer.edits

    return _Rule()


class _AttributeRenameTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, rule_id: str, old_name: str, new_name: str) -> None:
        self.rule_id = rule_id
        self.old_name = old_name
        self.new_name = new_name
        self.edits: list[RuleEdit] = []

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        if updated_node.attr.value != self.old_name:
            return updated_node
        # skip if this Attribute is itself the callee of a call (leave_Call's rename rules
        # own that case) — a bare attribute-access rename is for non-call usages only, e.g.
        # `for name in M.__fields__:`, not `M.some_method()`.
        new_node = updated_node.with_changes(attr=cst.Name(self.new_name))
        pos = self.get_metadata(PositionProvider, original_node)
        self.edits.append(
            RuleEdit(
                rule_id=self.rule_id,
                path="",
                line=pos.start.line,
                before=f"...{self.old_name}",
                after=f"...{self.new_name}",
            )
        )
        return new_node


def make_attribute_rename_rule(
    rule_id: str, description: str, confidence: Confidence, old_name: str, new_name: str
) -> CodemodRule:
    """Renames a bare attribute access (`X.old_name`, not `X.old_name(...)`)."""

    pattern = m.Attribute(attr=m.Name(value=old_name))

    class _Rule:
        def __init__(self) -> None:
            self.id = rule_id
            self.description = description
            self.confidence = confidence

        def applies(self, tree: cst.Module) -> bool:
            return bool(m.findall(tree, pattern))

        def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
            transformer = _AttributeRenameTransformer(rule_id, old_name, new_name)
            new_tree = MetadataWrapper(tree).visit(transformer)
            return new_tree, transformer.edits

    return _Rule()


MatcherPattern = m.BaseMatcherNode | m.MatchIfTrue[cst.CSTNode]


def make_flag_only_rule(
    rule_id: str, description: str, matcher: MatcherPattern, note: str
) -> CodemodRule:
    """A needs-review rule that detects a pattern and routes it to T2 without rewriting —
    docs/phase-3-loop.md: "needs-review rules should flag, not rewrite."

    Implemented via `findall` + `resolve(PositionProvider)` rather than a CSTVisitor whose
    `on_visit` calls `m.matches(node, matcher)` — verified directly that `m.matches()`
    does not evaluate a bare `MatchIfTrue` matcher the way `m.findall()` does (the same
    predicate returns True from `findall` and False from a per-node `matches()` check on
    the identical node); several rules here use `MatchIfTrue` for checks (like "has no
    default value") that aren't expressible as a plain structural matcher, so this had to
    be fixed rather than worked around per-rule.
    """

    class _Rule:
        def __init__(self) -> None:
            self.id = rule_id
            self.description = description
            self.confidence: Confidence = "needs-review"

        def applies(self, tree: cst.Module) -> bool:
            return bool(m.findall(tree, matcher))

        def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
            wrapper = MetadataWrapper(tree, unsafe_skip_copy=True)
            positions = wrapper.resolve(PositionProvider)
            edits = [
                RuleEdit(
                    rule_id=rule_id,
                    path="",
                    line=positions[node].start.line,
                    before="",
                    after="",
                    note=note,
                )
                for node in m.findall(wrapper.module, matcher)
            ]
            return tree, edits

    return _Rule()
