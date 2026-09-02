from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.config_class_to_configdict import rule


def test_orm_mode_renamed_to_from_attributes() -> None:
    src = "class M(BaseModel):\n    x: int\n\n    class Config:\n        orm_mode = True\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert "class Config" not in out
    assert "model_config = ConfigDict(from_attributes=True)" in out
    assert edits[0].rule_id == "config_class_to_configdict"


def test_allow_mutation_inverted_to_frozen() -> None:
    src = "class M(BaseModel):\n    class Config:\n        allow_mutation = False\n"
    out, _ = apply_rules(src, "f.py", [rule])
    assert "model_config = ConfigDict(frozen=True)" in out


def test_multiple_known_keys_combined() -> None:
    src = (
        "class M(BaseModel):\n"
        "    class Config:\n"
        "        orm_mode = True\n"
        "        arbitrary_types_allowed = True\n"
    )
    out, _ = apply_rules(src, "f.py", [rule])
    assert "from_attributes=True" in out
    assert "arbitrary_types_allowed=True" in out


def test_unrecognized_key_kept_and_flagged() -> None:
    src = "class M(BaseModel):\n    class Config:\n        some_future_option = 1\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert "some_future_option=1" in out  # kept, not silently dropped
    assert any("some_future_option" in (e.note or "") for e in edits)


def test_class_without_config_untouched() -> None:
    src = "class M(BaseModel):\n    x: int\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert edits == []


def test_other_class_body_members_preserved() -> None:
    src = (
        "class M(BaseModel):\n"
        "    x: int\n"
        "    y: str\n\n"
        "    class Config:\n"
        "        orm_mode = True\n\n"
        "    def method(self):\n"
        "        return self.x\n"
    )
    out, _ = apply_rules(src, "f.py", [rule])
    assert "x: int" in out
    assert "y: str" in out
    assert "def method(self):" in out
    assert "return self.x" in out


# --- ConfigDict import insertion (found missing against a real corpus repo) --------


def test_configdict_import_inserted_when_no_imports_exist() -> None:
    src = "class M(BaseModel):\n    class Config:\n        orm_mode = True\n"
    out, _ = apply_rules(src, "f.py", [rule])
    assert "from pydantic import ConfigDict" in out
    compile(out, "f.py", "exec")


def test_configdict_added_to_existing_pydantic_import() -> None:
    src = (
        "from pydantic import BaseModel\n\n"
        "class M(BaseModel):\n    class Config:\n        orm_mode = True\n"
    )
    out, _ = apply_rules(src, "f.py", [rule])
    assert "from pydantic import BaseModel, ConfigDict" in out
    assert out.count("import") == 1  # extended the existing line, not a new one


def test_configdict_not_duplicated_when_already_imported() -> None:
    src = (
        "from pydantic import BaseModel, ConfigDict\n\n"
        "class M(BaseModel):\n    class Config:\n        orm_mode = True\n"
    )
    out, _ = apply_rules(src, "f.py", [rule])
    assert out.count("ConfigDict") == 2  # once in the import, once in the call


def test_no_import_added_when_rule_does_not_fire() -> None:
    src = "class M(BaseModel):\n    x: int\n"
    out, _ = apply_rules(src, "f.py", [rule])
    assert "ConfigDict" not in out


def test_real_world_shape_from_madkote_fastapi_plugins_config() -> None:
    # the exact pattern from fastapi_plugins/plugin.py that hit NameError before this fix
    src = (
        "import pydantic\n\n\n"
        "class PluginSettings(pydantic.BaseSettings):\n"
        "    class Config:\n"
        "        env_prefix = ''\n"
        "        use_enum_values = True\n"
    )
    out, _ = apply_rules(src, "plugin.py", [rule])
    assert "from pydantic import ConfigDict" in out
    assert "model_config = ConfigDict(env_prefix=''" in out
    compile(out, "plugin.py", "exec")
