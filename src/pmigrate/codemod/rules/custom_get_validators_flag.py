"""Detects `__get_validators__` (the v1 custom-type validation protocol) and flags it
needs-review (docs/phase-3-loop.md T1 table). v2's replacement, `__get_pydantic_core_schema__`,
is a different protocol entirely — a different signature, a different return shape based on
pydantic-core's schema builders, not a compatible rename. Highest difficulty score in
relevance.py's signal table (est_difficulty=3) for the same reason: this is real redesign
work, not something a codemod should attempt."""

import libcst.matchers as m

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_flag_only_rule

_pattern = m.FunctionDef(name=m.Name(value="__get_validators__"))

rule: CodemodRule = make_flag_only_rule(
    rule_id="custom_get_validators_flag",
    description="__get_validators__ needs a full rewrite to __get_pydantic_core_schema__",
    matcher=_pattern,
    note="different protocol entirely in v2, not a compatible rename — needs a T2/human pass",
)
