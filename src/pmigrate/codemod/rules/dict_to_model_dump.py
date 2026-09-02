"""`m.dict()` -> `m.model_dump()` (docs/phase-3-loop.md T1 table). Pure rename, no
signature change between v1 and v2 for the common case."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="dict_to_model_dump",
    description="m.dict() -> m.model_dump()",
    confidence="mechanical",
    old_name="dict",
    new_name="model_dump",
)
