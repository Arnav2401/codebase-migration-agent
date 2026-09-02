from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules.basesettings_import import rule


def test_splits_import_when_other_names_present() -> None:
    src = "from pydantic import BaseModel, BaseSettings\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == "from pydantic import BaseModel\nfrom pydantic_settings import BaseSettings\n"
    assert len(edits) == 1


def test_replaces_import_when_basesettings_is_only_name() -> None:
    src = "from pydantic import BaseSettings\n"
    out, _ = apply_rules(src, "f.py", [rule])
    assert out == "from pydantic_settings import BaseSettings\n"


def test_does_not_touch_unrelated_imports() -> None:
    src = "from pydantic import BaseModel\nfrom typing import Optional\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert out == src
    assert edits == []


def test_class_using_basesettings_is_preserved_after_split() -> None:
    src = "from pydantic import BaseSettings\n\nclass S(BaseSettings):\n    x: int\n"
    out, _ = apply_rules(src, "f.py", [rule])
    assert "from pydantic_settings import BaseSettings" in out
    assert "class S(BaseSettings):" in out
    assert "x: int" in out


# --- qualified `pydantic.BaseSettings` usage (found against a real corpus repo) ----


def test_qualified_pydantic_basesettings_rewritten() -> None:
    src = "import pydantic\n\nclass X(pydantic.BaseSettings):\n    pass\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert "import pydantic_settings" in out
    assert "class X(pydantic_settings.BaseSettings):" in out
    assert "import pydantic\n" in out  # original import is NOT removed
    assert any(e.before == "pydantic.BaseSettings" for e in edits)


def test_qualified_form_import_inserted_after_last_import() -> None:
    src = "import os\nimport pydantic\n\nclass X(pydantic.BaseSettings):\n    pass\n"
    out, _ = apply_rules(src, "f.py", [rule])
    lines = out.splitlines()
    assert lines[0] == "import os"
    assert lines[1] == "import pydantic"
    assert lines[2] == "import pydantic_settings"


def test_no_import_inserted_when_no_qualified_usage() -> None:
    # regression check: don't add `import pydantic_settings` when nothing needs it
    src = "import pydantic\n\nx: pydantic.BaseModel = None\n"
    out, edits = apply_rules(src, "f.py", [rule])
    assert "pydantic_settings" not in out
    assert edits == []


def test_real_world_shape_from_madkote_fastapi_plugins() -> None:
    # the exact pattern that slipped through before this fix — fastapi_plugins/plugin.py
    # at pre_sha 26f31177634ba84ca73c63f84535af205135d781
    src = (
        "import pydantic\n\n\n"
        "class PluginSettings(pydantic.BaseSettings):\n"
        "    class Config:\n"
        "        env_prefix = ''\n\n\n"
        "class Plugin:\n"
        "    DEFAULT_CONFIG_CLASS: pydantic.BaseSettings = None\n"
    )
    out, edits = apply_rules(src, "plugin.py", [rule])
    assert "class PluginSettings(pydantic_settings.BaseSettings):" in out
    assert "DEFAULT_CONFIG_CLASS: pydantic_settings.BaseSettings = None" in out
    assert len(edits) == 2  # both usages rewritten, one import inserted
    compile(out, "plugin.py", "exec")
