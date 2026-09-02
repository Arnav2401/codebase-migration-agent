from pathlib import Path

from pmigrate.agent.repair import (
    build_repair_prompt,
    collect_failure_texts,
    extract_rewritten_files,
    extract_target_file,
    find_related_files,
    repair_system_prompt,
)
from pmigrate.types import TestOutcome, TestRun

# the exact real traceback shape found against madkote/fastapi-plugins (docs/decisions.md
# D19): the crash is INSIDE first-party code (a bad type annotation evaluated at class-body
# time), so the traceback names the file directly.
_BASESETTINGS_TRACEBACK = """\
tests/test_control.py:15: in <module>
    import fastapi_plugins
fastapi_plugins/__init__.py:22: in <module>
    from .settings import *
fastapi_plugins/settings.py:53: in <module>
    class ConfigManager(object):
fastapi_plugins/settings.py:57: in ConfigManager
    def register(self, name: str, config: pydantic.BaseSettings) -> None:
/usr/local/lib/python3.11/site-packages/pydantic/__init__.py:437: in __getattr__
    return _getattr_migration(attr_name)
E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved to the \
`pydantic-settings` package.\
"""

# the exact real traceback shape for the OTHER failure class found (docs/decisions.md D20):
# a ValidationError raised at INSTANTIATION time. The only first-party frame is the test
# file itself — the class definition never appears as a path at all.
_VALIDATION_ERROR_TRACEBACK = """\
tests/test_redis.py:35: in <module>
    fastapi_plugins.RedisSettings(redis_url='redis://localhost:6379/1')
/usr/local/lib/python3.11/site-packages/pydantic_settings/main.py:262: in __init__
    super().__init__(**__pydantic_self__.__class__._settings_build_values(sources, init_kwargs))
E   pydantic_core._pydantic_core.ValidationError: 5 validation errors for RedisSettings
E   redis_user
E     Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]\
"""


def _outcome(traceback: str, status: str = "failed") -> TestOutcome:
    return TestOutcome("t.py::test_x", status, 0.1, "boom", traceback, None)  # type: ignore[arg-type]


def test_collect_failure_texts_includes_failed_and_error_outcomes_and_collection_errors() -> None:
    run = TestRun(
        outcomes=(
            _outcome("failed traceback", status="failed"),
            _outcome("error traceback", status="error"),
            TestOutcome("t.py::test_pass", "passed", 0.1, None, "should not appear", None),
        ),
        collection_errors=("a collection error",),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    texts = collect_failure_texts(run)
    assert any("failed traceback" in t for t in texts)
    assert any("error traceback" in t for t in texts)
    assert "a collection error" in texts
    assert not any("should not appear" in t for t in texts)


def test_extract_target_file_finds_first_party_path_in_traceback() -> None:
    target = extract_target_file((_BASESETTINGS_TRACEBACK,), Path("/unused"))
    assert target == "fastapi_plugins/settings.py"


def test_extract_target_file_excludes_test_paths_from_strategy_one(tmp_path: Path) -> None:
    (tmp_path / "fastapi_plugins").mkdir()
    (tmp_path / "fastapi_plugins" / "_redis.py").write_text(
        "class RedisSettings(BaseSettings):\n    pass\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_redis.py").write_text("# test file\n")

    target = extract_target_file((_VALIDATION_ERROR_TRACEBACK,), tmp_path)

    # the only path literally in the traceback is the test file, which must be excluded —
    # falls through to strategy 2 (grep for the class named in pydantic's own error message)
    assert target == "fastapi_plugins/_redis.py"


def test_extract_target_file_returns_none_when_class_not_found(tmp_path: Path) -> None:
    (tmp_path / "empty.py").write_text("x = 1\n")
    target = extract_target_file((_VALIDATION_ERROR_TRACEBACK,), tmp_path)
    assert target is None


def test_extract_target_file_skips_missing_third_party_module_failures(tmp_path: Path) -> None:
    # the exact real shape found live (docs/decisions.md D26): a legitimate first-party
    # frame (a deliberate `raise RuntimeError(...)` guard) sits right next to a
    # ModuleNotFoundError for a package that was simply never installed. No rewrite of
    # this file can fix that — repair() must not target it at all.
    aiomcache_traceback = (
        "fastapi_plugins/memcached.py:10: in <module>\n"
        "    import aiomcache\n"
        "E   ModuleNotFoundError: No module named 'aiomcache'\n\n"
        "During handling of the above exception, another exception occurred:\n"
        "tests/test_control.py:18: in <module>\n"
        "    from fastapi_plugins.memcached import memcached_plugin\n"
        "fastapi_plugins/memcached.py:12: in <module>\n"
        "    raise RuntimeError('aiomcache is not installed')\n"
        "E   RuntimeError: aiomcache is not installed"
    )
    assert extract_target_file((aiomcache_traceback,), tmp_path) is None


def test_extract_target_file_finds_the_real_bug_alongside_an_unfixable_one(
    tmp_path: Path,
) -> None:
    # with a mix of one unfixable (missing dependency) and one real, fixable failure, the
    # real one must still be found — the whole point of filtering is to not let the
    # unfixable one crowd out a target that repair() could actually act on.
    aiomcache_traceback = (
        "fastapi_plugins/memcached.py:10: in <module>\n"
        "    import aiomcache\n"
        "E   ModuleNotFoundError: No module named 'aiomcache'"
    )
    target = extract_target_file((aiomcache_traceback, _BASESETTINGS_TRACEBACK), tmp_path)
    assert target == "fastapi_plugins/settings.py"


def test_extract_target_file_returns_none_for_unrecognized_failure_shape(tmp_path: Path) -> None:
    target = extract_target_file(
        ("some generic assertion failure with no path or class",), tmp_path
    )
    assert target is None


def test_build_repair_prompt_includes_path_content_and_failures() -> None:
    prompt = build_repair_prompt({"app/models.py": "x = 1\n"}, ("failure detail here",))
    assert "app/models.py" in prompt
    assert "x = 1" in prompt
    assert "failure detail here" in prompt


def test_build_repair_prompt_includes_every_file_when_multiple_given() -> None:
    prompt = build_repair_prompt(
        {"app/models.py": "x = 1\n", "app/base.py": "y = 2\n"}, ("failure detail",)
    )
    assert "app/models.py" in prompt
    assert "x = 1" in prompt
    assert "app/base.py" in prompt
    assert "y = 2" in prompt


def test_extract_rewritten_files_parses_a_single_file_block() -> None:
    response = "File: app/models.py\n```python\nx: str | None = None\n```\n"
    result = extract_rewritten_files(response)
    assert result == {"app/models.py": "x: str | None = None\n"}


def test_extract_rewritten_files_parses_multiple_file_blocks() -> None:
    response = (
        "File: fastapi_plugins/_redis.py\n"
        "```python\nredis_url: str | None = None\n```\n\n"
        "File: demo.py\n"
        "```python\nx = 1\n```\n"
    )
    result = extract_rewritten_files(response)
    assert result == {
        "fastapi_plugins/_redis.py": "redis_url: str | None = None\n",
        "demo.py": "x = 1\n",
    }


def test_extract_rewritten_files_returns_empty_dict_without_a_code_block() -> None:
    assert extract_rewritten_files("I cannot help with that.") == {}


def test_find_related_files_finds_a_base_class_defined_in_another_file(tmp_path: Path) -> None:
    # the exact real shape found live (docs/decisions.md D26/D28): fastapi_plugins/
    # demo.py's AppSettings inherits fastapi_plugins.RedisSettings, and the fields
    # actually causing a validation error are declared on RedisSettings, in a
    # different file (fastapi_plugins/_redis.py) than the one that merely inherits it.
    (tmp_path / "fastapi_plugins").mkdir()
    (tmp_path / "fastapi_plugins" / "_redis.py").write_text(
        "class RedisSettings(BaseSettings):\n    redis_url: str = None\n"
    )
    demo_content = (
        "import fastapi_plugins\n\n\n"
        "class AppSettings(\n"
        "    OtherSettings,\n"
        "    fastapi_plugins.RedisSettings,\n"
        "):\n"
        "    api_name: str = 'x'\n"
    )
    (tmp_path / "demo.py").write_text(demo_content)

    related = find_related_files("demo.py", demo_content, tmp_path)

    assert related == ("fastapi_plugins/_redis.py",)


def test_find_related_files_excludes_well_known_pydantic_bases(tmp_path: Path) -> None:
    content = "class Foo(BaseModel):\n    x: int = 1\n"
    (tmp_path / "foo.py").write_text(content)
    assert find_related_files("foo.py", content, tmp_path) == ()


def test_find_related_files_returns_empty_when_base_not_found_anywhere(tmp_path: Path) -> None:
    content = "class Foo(SomeUndefinedBase):\n    x: int = 1\n"
    (tmp_path / "foo.py").write_text(content)
    assert find_related_files("foo.py", content, tmp_path) == ()


def test_find_related_files_excludes_the_target_file_itself(tmp_path: Path) -> None:
    # a class that inherits from ANOTHER class defined in the SAME file shouldn't cause
    # that file to be listed as its own "related" file
    content = "class Base:\n    pass\n\n\nclass Foo(Base):\n    x: int = 1\n"
    (tmp_path / "foo.py").write_text(content)
    assert find_related_files("foo.py", content, tmp_path) == ()


def test_repair_system_prompt_is_loaded_from_a_real_file_not_inlined() -> None:
    # CLAUDE.md: "Prompts live in src/pmigrate/agent/prompts/*.md ... Never inline a
    # prompt in Python."
    prompt = repair_system_prompt()
    assert "pydantic" in prompt.lower()
    assert len(prompt) > 50
