"""`m.copy(update=...)` -> `m.model_copy(update=...)` (docs/phase-3-loop.md T1 table).
"likely" not "mechanical": `.copy()` is also a builtin dict/list method, so this rule can
fire on a non-model `.copy()` call — the test-gated loop (protocol.py's module docstring)
is what catches that, not this rule's own precision."""

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_call_rename_rule

rule: CodemodRule = make_call_rename_rule(
    rule_id="copy_to_model_copy",
    description="m.copy(update=...) -> m.model_copy(update=...)",
    confidence="likely",
    old_name="copy",
    new_name="model_copy",
)
