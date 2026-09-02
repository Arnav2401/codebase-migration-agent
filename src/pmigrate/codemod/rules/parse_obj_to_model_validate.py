"""`M.parse_obj(d)` -> `M.model_validate(d)` (docs/phase-3-loop.md T1 table)."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="parse_obj_to_model_validate",
    description="M.parse_obj(d) -> M.model_validate(d)",
    confidence="mechanical",
    old_name="parse_obj",
    new_name="model_validate",
)
