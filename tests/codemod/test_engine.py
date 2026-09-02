import libcst as cst

from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.protocol import CodemodRule, Confidence, RuleEdit
from pmigrate.codemod.rules import ALL_RULES
from pmigrate.codemod.rules.dict_to_model_dump import rule as dict_to_model_dump_rule


class _ExplodingRule:
    id = "exploding_rule"
    description = "always raises — test double for an unanticipated-shape crash"
    confidence: Confidence = "mechanical"

    def applies(self, tree: cst.Module) -> bool:
        return True

    def apply(self, tree: cst.Module) -> tuple[cst.Module, list[RuleEdit]]:
        raise AssertionError("simulated: rule hit a shape it didn't anticipate")


exploding_rule: CodemodRule = _ExplodingRule()

KITCHEN_SINK_V1 = """\
from pydantic import BaseModel, BaseSettings, Field, validator


class Settings(BaseSettings):
    name: str


class User(BaseModel):
    id: int
    nickname: Optional[str]
    email: str = Field(regex="^\\\\S+@\\\\S+$")

    class Config:
        orm_mode = True

    @validator("email")
    def check_email(cls, v):
        return v.lower()

    def to_payload(self):
        return self.dict()
"""


def test_all_rules_registered_with_required_attributes() -> None:
    assert len(ALL_RULES) >= 14
    ids = [r.id for r in ALL_RULES]
    assert len(ids) == len(set(ids)), "duplicate rule ids"
    for r in ALL_RULES:
        assert r.confidence in ("mechanical", "likely", "needs-review")
        assert r.description


def test_kitchen_sink_file_migrates_mechanically_where_possible() -> None:
    out, edits = apply_rules(KITCHEN_SINK_V1, "user.py", ALL_RULES)

    # rewritten
    assert "from pydantic_settings import BaseSettings" in out
    assert "model_config = ConfigDict(from_attributes=True)" in out
    assert "class Config" not in out
    assert "@field_validator" in out and "@classmethod" in out
    assert 'Field(pattern="^\\\\S+@\\\\S+$")' in out
    assert "self.model_dump()" in out

    # every edit is attributed to this exact file
    assert all(e.path == "user.py" for e in edits)
    fired_rule_ids = {e.rule_id for e in edits}
    assert "basesettings_import_to_pydantic_settings" in fired_rule_ids
    assert "config_class_to_configdict" in fired_rule_ids
    assert "validator_to_field_validator" in fired_rule_ids
    assert "field_v1_kwargs" in fired_rule_ids
    assert "dict_to_model_dump" in fired_rule_ids

    # implicit Optional[str] with no default is flagged, not silently rewritten
    assert "implicit_optional_default_flag" in fired_rule_ids
    assert "nickname: Optional[str]" in out  # left exactly as-is


def test_output_is_valid_python_after_full_pipeline() -> None:
    out, _ = apply_rules(KITCHEN_SINK_V1, "user.py", ALL_RULES)
    compile(out, "user.py", "exec")  # raises SyntaxError if the rewrite produced garbage


def test_running_twice_is_idempotent() -> None:
    out1, _ = apply_rules(KITCHEN_SINK_V1, "user.py", ALL_RULES)
    out2, edits2 = apply_rules(out1, "user.py", ALL_RULES)
    assert out1 == out2  # a second pass changes no code

    # the flag-only detectors correctly re-flag what they can't fix (nickname is still
    # bare-Optional after the first pass); the mechanical renames must NOT fire again,
    # since there's no more `.dict()`/`class Config`/etc. left to rewrite.
    fired_again = {e.rule_id for e in edits2}
    assert "implicit_optional_default_flag" in fired_again
    assert "dict_to_model_dump" not in fired_again
    assert "config_class_to_configdict" not in fired_again
    assert "basesettings_import_to_pydantic_settings" not in fired_again


def test_a_rule_that_crashes_does_not_abort_the_other_rules() -> None:
    # the exact D22 failure mode: `validator_to_field_validator` hit a real-world shape it
    # didn't anticipate and raised, which — before this fix — aborted `apply_rules`
    # entirely, discarding every OTHER rule's already-computed, independent, correct edit
    # for the same file. One rule's wrong assumption must not cost the whole file's fixes.
    src = "x = m.dict()\n"
    out, edits = apply_rules(src, "f.py", [exploding_rule, dict_to_model_dump_rule])

    assert out == "x = m.model_dump()\n"
    assert [e.rule_id for e in edits] == ["dict_to_model_dump"]
