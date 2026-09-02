"""Detects `@root_validator` and flags it needs-review without rewriting (docs/phase-3-loop.md
T1 table: "needs-review — mode depends on pre="). Whether it becomes
`@model_validator(mode="before")` or `@model_validator(mode="after")` depends on the
`pre=` kwarg (and its default has flipped between pydantic versions), so guessing wrong
here silently changes validation ORDER, not just syntax — worth a human or T2 pass rather
than a confident-looking auto-rewrite."""

import libcst.matchers as m

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_flag_only_rule

_pattern = m.Decorator(
    decorator=m.OneOf(
        m.Call(func=m.Name(value="root_validator")),
        m.Name(value="root_validator"),
    )
)

rule: CodemodRule = make_flag_only_rule(
    rule_id="root_validator_flag",
    description="@root_validator needs manual review before becoming @model_validator",
    matcher=_pattern,
    note='mode="before"/"after" depends on the original pre= kwarg — not auto-rewritten',
)
