"""`m.json()` -> `m.model_dump_json()` (docs/phase-3-loop.md T1 table)."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="json_to_model_dump_json",
    description="m.json() -> m.model_dump_json()",
    confidence="mechanical",
    old_name="json",
    new_name="model_dump_json",
)
