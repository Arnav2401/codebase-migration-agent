from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.copy_to_model_copy import rule as copy_rule
from pmigrate.codemod.rules.dict_to_model_dump import rule as dict_rule
from pmigrate.codemod.rules.fields_attr import rule as fields_attr_rule
from pmigrate.codemod.rules.json_to_model_dump_json import rule as json_rule
from pmigrate.codemod.rules.parse_obj_to_model_validate import rule as parse_obj_rule
from pmigrate.codemod.rules.parse_raw_to_validate_json import rule as parse_raw_rule
from pmigrate.codemod.rules.update_forward_refs import rule as update_forward_refs_rule


def test_dict_to_model_dump() -> None:
    src = "d = m.dict()\n"
    out, edits = apply_rules(src, "f.py", [dict_rule])
    assert out == "d = m.model_dump()\n"
    assert len(edits) == 1 and edits[0].rule_id == "dict_to_model_dump" and edits[0].path == "f.py"


def test_dict_rule_does_not_fire_on_unrelated_code() -> None:
    src = "d = {'a': 1}\nprint(d)\n"
    out, edits = apply_rules(src, "f.py", [dict_rule])
    assert out == src
    assert edits == []


def test_json_to_model_dump_json() -> None:
    out, edits = apply_rules("s = m.json()\n", "f.py", [json_rule])
    assert out == "s = m.model_dump_json()\n"
    assert edits[0].rule_id == "json_to_model_dump_json"


def test_parse_obj_to_model_validate() -> None:
    out, _ = apply_rules("obj = M.parse_obj(data)\n", "f.py", [parse_obj_rule])
    assert out == "obj = M.model_validate(data)\n"


def test_parse_raw_to_validate_json() -> None:
    out, edits = apply_rules("obj = M.parse_raw(s)\n", "f.py", [parse_raw_rule])
    assert out == "obj = M.model_validate_json(s)\n"
    assert edits[0].rule_id == "parse_raw_to_validate_json"


def test_copy_to_model_copy() -> None:
    out, _ = apply_rules("m2 = m.copy(update={'x': 1})\n", "f.py", [copy_rule])
    assert out == "m2 = m.model_copy(update={'x': 1})\n"


def test_update_forward_refs_to_model_rebuild() -> None:
    out, _ = apply_rules("M.update_forward_refs()\n", "f.py", [update_forward_refs_rule])
    assert out == "M.model_rebuild()\n"


def test_fields_attr_rename_bare_access() -> None:
    src = "for name in M.__fields__:\n    print(name)\n"
    out, edits = apply_rules(src, "f.py", [fields_attr_rule])
    assert out == "for name in M.model_fields:\n    print(name)\n"
    assert edits[0].rule_id == "fields_attr_to_model_fields"


def test_multiple_rules_chain_in_one_pass() -> None:
    src = "d = m.dict()\ns = m.json()\n"
    out, edits = apply_rules(src, "f.py", [dict_rule, json_rule])
    assert out == "d = m.model_dump()\ns = m.model_dump_json()\n"
    assert {e.rule_id for e in edits} == {"dict_to_model_dump", "json_to_model_dump_json"}
