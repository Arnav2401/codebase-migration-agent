from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.custom_get_validators_flag import rule as get_validators_rule
from pmigrate.codemod.rules.implicit_optional_flag import rule as implicit_optional_rule
from pmigrate.codemod.rules.json_encoders_flag import rule as json_encoders_rule
from pmigrate.codemod.rules.root_validator_flag import rule as root_validator_rule


def test_root_validator_flagged_not_rewritten() -> None:
    src = (
        "class M(BaseModel):\n    @root_validator\n"
        "    def check(cls, values):\n        return values\n"
    )
    out, edits = apply_rules(src, "f.py", [root_validator_rule])
    assert out == src  # detector-only: source is never rewritten
    assert len(edits) == 1
    assert edits[0].before == ""  # flag-only edits carry no rewrite text
    assert edits[0].note is not None and "pre=" in edits[0].note


def test_root_validator_with_call_form_also_flagged() -> None:
    src = (
        "class M(BaseModel):\n    @root_validator(pre=True)\n"
        "    def check(cls, values):\n        return values\n"
    )
    _, edits = apply_rules(src, "f.py", [root_validator_rule])
    assert len(edits) == 1


def test_plain_validator_not_flagged_by_root_validator_rule() -> None:
    src = "class M(BaseModel):\n    @validator('x')\n    def check(cls, v):\n        return v\n"
    out, edits = apply_rules(src, "f.py", [root_validator_rule])
    assert out == src
    assert edits == []


def test_get_validators_flagged() -> None:
    src = (
        "class Custom:\n    @classmethod\n"
        "    def __get_validators__(cls):\n        yield cls.validate\n"
    )
    _, edits = apply_rules(src, "f.py", [get_validators_rule])
    assert len(edits) == 1
    assert "different protocol entirely" in edits[0].note


def test_json_encoders_flagged() -> None:
    src = "class M(BaseModel):\n    class Config:\n        json_encoders = {datetime: str}\n"
    _, edits = apply_rules(src, "f.py", [json_encoders_rule])
    assert len(edits) == 1
    assert "field_serializer" in edits[0].note


def test_implicit_optional_bare_flagged() -> None:
    src = "class M(BaseModel):\n    x: Optional[int]\n"
    _, edits = apply_rules(src, "f.py", [implicit_optional_rule])
    assert len(edits) == 1


def test_implicit_optional_pipe_none_flagged() -> None:
    src = "class M(BaseModel):\n    x: int | None\n"
    _, edits = apply_rules(src, "f.py", [implicit_optional_rule])
    assert len(edits) == 1


def test_optional_with_explicit_default_not_flagged() -> None:
    src = "class M(BaseModel):\n    x: Optional[int] = None\n"
    _, edits = apply_rules(src, "f.py", [implicit_optional_rule])
    assert edits == []


def test_non_optional_field_not_flagged() -> None:
    src = "class M(BaseModel):\n    x: int\n"
    _, edits = apply_rules(src, "f.py", [implicit_optional_rule])
    assert edits == []
