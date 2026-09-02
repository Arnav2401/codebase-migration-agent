from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.validator_to_field_validator import rule


def test_validator_renamed_and_classmethod_added() -> None:
    src = "class M(BaseModel):\n    @validator('x')\n    def check(cls, v):\n        return v\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert "@field_validator('x')" in out
    assert "@classmethod" in out
    assert out.index("@field_validator") < out.index("@classmethod") < out.index("def check")
    assert edits[0].rule_id == "validator_to_field_validator"


def test_existing_classmethod_not_duplicated() -> None:
    src = (
        "class M(BaseModel):\n"
        "    @validator('x')\n"
        "    @classmethod\n"
        "    def check(cls, v):\n"
        "        return v\n"
    )
    out, _ = apply_rules(src, "f.py", [rule])
    assert out.count("@classmethod") == 1
    assert "@field_validator('x')" in out


def test_values_parameter_flagged_in_note() -> None:
    src = (
        "class M(BaseModel):\n    @validator('x')\n"
        "    def check(cls, v, values):\n        return v\n"
    )
    _, edits = apply_rules(src, "f.py", [rule])
    assert any("info.data" in (e.note or "") for e in edits)


def test_root_validator_not_touched_by_this_rule() -> None:
    src = (
        "class M(BaseModel):\n    @root_validator\n"
        "    def check(cls, values):\n        return values\n"
    )
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert edits == []


def test_bare_validator_name_from_unrelated_decorator_left_untouched() -> None:
    # the exact real-world shape from `plugboard-schemas` (docs/decisions.md D22):
    # `from ._validator_registry import validator` is a LOCAL decorator, completely
    # unrelated to pydantic, applied bare (no call) — `@validator("x")` is the only valid
    # pydantic v1 shape, so a bare `@validator` can never actually be pydantic's. This
    # used to crash with `AssertionError` (the rule assumed every `validator`-named
    # decorator was a Call); it must now be left alone instead.
    src = (
        "from ._validator_registry import validator\n\n\n"
        "@validator\n"
        "def check_thing(value):\n"
        "    return value\n"
    )
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert edits == []
