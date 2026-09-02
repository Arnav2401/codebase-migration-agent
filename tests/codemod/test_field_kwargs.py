from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.field_kwargs import rule


def test_regex_renamed_to_pattern() -> None:
    out, edits = apply_rules("x: str = Field(regex='^a')\n", "f.py", [rule])
    assert out == "x: str = Field(pattern='^a')\n"
    assert edits[0].rule_id == "field_v1_kwargs"


def test_min_items_and_max_items_renamed() -> None:
    out, _ = apply_rules("x: list = Field(min_items=1, max_items=10)\n", "f.py", [rule])
    assert out == "x: list = Field(min_length=1, max_length=10)\n"


def test_allow_mutation_literal_bool_inverted_to_frozen() -> None:
    out, edits = apply_rules("x: int = Field(allow_mutation=False)\n", "f.py", [rule])
    assert out == "x: int = Field(frozen=True)\n"
    assert any("inverted" in (e.note or "") for e in edits)


def test_allow_mutation_non_literal_flagged_not_rewritten() -> None:
    src = "x: int = Field(allow_mutation=some_flag)\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src  # NOT rewritten — can't safely invert a non-literal value
    assert any("not a literal True/False" in (e.note or "") for e in edits)


def test_const_flagged_and_left_untouched() -> None:
    src = "x: int = Field(const=5)\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert any("Literal" in (e.note or "") for e in edits)


def test_unique_items_flagged_and_left_untouched() -> None:
    src = "x: list = Field(unique_items=True)\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert any("removed" in (e.note or "") for e in edits)


def test_unrelated_field_call_untouched() -> None:
    src = "x: int = Field(default=1, description='ok')\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert edits == []


def test_mixed_kwargs_only_rewrites_known_renames() -> None:
    src = "x: str = Field(regex='^a', default='a', const=1)\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == "x: str = Field(pattern='^a', default='a', const=1)\n"
    rule_ids_and_notes = [(e.before, e.note) for e in edits]
    assert ("regex=...", None) in rule_ids_and_notes
    assert any(note and "Literal" in note for _, note in rule_ids_and_notes)
