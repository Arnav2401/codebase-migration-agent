"""Detects a `json_encoders` assignment (v1 Config key, or a ConfigDict kwarg after
config_class_to_configdict already ran) and flags it needs-review (docs/phase-3-loop.md T1
table). v2 replaces per-type JSON encoders with per-field serializers
(`@field_serializer`) — a redesign of *how* serialization is customized, not a kwarg or
call rename, so this rule only detects and flags rather than rewriting.
"""

import libcst.matchers as m

from pmigrate.codemod.protocol import CodemodRule
from pmigrate.codemod.rules._common import make_flag_only_rule

_pattern = m.Assign(targets=[m.AssignTarget(target=m.Name(value="json_encoders"))])

rule: CodemodRule = make_flag_only_rule(
    rule_id="json_encoders_flag",
    description="json_encoders needs a redesign to @field_serializer, not a rename",
    matcher=_pattern,
    note="v2 moved per-type JSON encoders to per-field @field_serializer — needs a T2/human pass",
)
