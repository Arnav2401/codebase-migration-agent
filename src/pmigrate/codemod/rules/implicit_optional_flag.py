"""Detects `x: Optional[T]` (or `x: T | None`) with no explicit default and flags it
needs-review (docs/phase-3-loop.md T1 table calls this "the classic silent breakage").

v1 treated an `Optional`-annotated field with no default as implicitly defaulting to
`None`; v2 requires the default to be explicit (`= None`) or the field becomes required.
This is silent because it doesn't raise a SyntaxError or an import-time error — it changes
runtime behavior (a previously-optional field becomes required), which only shows up when
something tries to construct the model without that field and gets a ValidationError that
looks unrelated to "the migration." Not auto-rewritten: adding `= None` is usually right,
but not always (sometimes the omitted default was a bug in the v1 code, and the field
really should be required) — a judgment call, not a mechanical fact.
"""

from __future__ import annotations

import libcst as cst
import libcst.matchers as m

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_flag_only_rule


def _is_bare_optional_annassign(node: cst.CSTNode) -> bool:
    if not isinstance(node, cst.AnnAssign) or node.value is not None:
        return False
    ann = node.annotation.annotation
    if (
        isinstance(ann, cst.Subscript)
        and isinstance(ann.value, cst.Name)
        and ann.value.value == "Optional"
    ):
        return True
    if isinstance(ann, cst.BinaryOperation) and isinstance(ann.operator, cst.BitOr):
        left_none = isinstance(ann.left, cst.Name) and ann.left.value == "None"
        right_none = isinstance(ann.right, cst.Name) and ann.right.value == "None"
        return left_none or right_none
    return False


_pattern = m.MatchIfTrue(_is_bare_optional_annassign)

rule: CodemodRule = make_flag_only_rule(
    rule_id="implicit_optional_default_flag",
    description="Optional[T] field with no explicit default silently becomes required in v2",
    matcher=_pattern,
    note="v1 implicitly defaulted this to None; v2 requires the default to be explicit — "
    "add `= None` if that's the intended behavior, needs a human judgment call",
)
