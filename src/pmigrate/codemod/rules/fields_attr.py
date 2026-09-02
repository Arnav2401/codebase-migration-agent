"""`M.__fields__` -> `M.model_fields` (docs/phase-3-loop.md T1 table). A bare attribute
access, not a call — uses the attribute-rename transformer, not the call-rename one."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_attribute_rename_rule

rule: CodemodRule = make_attribute_rename_rule(
    rule_id="fields_attr_to_model_fields",
    description="M.__fields__ -> M.model_fields",
    confidence="mechanical",
    old_name="__fields__",
    new_name="model_fields",
)
