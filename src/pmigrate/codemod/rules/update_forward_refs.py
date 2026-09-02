"""`M.update_forward_refs()` -> `M.model_rebuild()` (docs/phase-3-loop.md T1 table)."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="update_forward_refs_to_model_rebuild",
    description="M.update_forward_refs() -> M.model_rebuild()",
    confidence="mechanical",
    old_name="update_forward_refs",
    new_name="model_rebuild",
)
