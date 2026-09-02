"""`M.parse_raw(s)` -> `M.model_validate_json(s)` (docs/phase-3-loop.md T1 table).
"likely" not "mechanical": parse_raw accepted a `content_type` kwarg for non-JSON payloads
that model_validate_json doesn't have — the rename is right for the common (JSON) case but
worth a second look if that kwarg is present."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="parse_raw_to_validate_json",
    description="M.parse_raw(s) -> M.model_validate_json(s)",
    confidence="likely",
    old_name="parse_raw",
    new_name="model_validate_json",
)
