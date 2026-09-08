from pathlib import Path

from pmigrate.agent.repair import (
    PromptBudget,
    build_repair_prompt,
    collect_failure_texts,
    extract_rewritten_files,
    extract_target_file,
    files_in_traceback,
    find_related_files,
    repair_system_prompt,
    target_exceeds_budget,
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
    prompt = build_repair_prompt({"app/models.py": "x = 1\n"}, ("failure detail here",)).text
    assert "app/models.py" in prompt
    assert "x = 1" in prompt
    assert "failure detail here" in prompt


def test_build_repair_prompt_includes_every_file_when_multiple_given() -> None:
    prompt = build_repair_prompt(
        {"app/models.py": "x = 1\n", "app/base.py": "y = 2\n"}, ("failure detail",)
    ).text
    assert "app/models.py" in prompt
    assert "x = 1" in prompt
    assert "app/base.py" in prompt
    assert "y = 2" in prompt


# --- prompt budget (docs/decisions.md D75) ------------------------------------------


def test_build_repair_prompt_without_a_budget_drops_nothing() -> None:
    """The uncapped default must stay byte-identical to pre-D75 behavior, since every
    existing arm's results were produced under it."""
    built = build_repair_prompt(
        {"app/models.py": "x = 1\n", "app/base.py": "y" * 100_000},
        ("f" * 100_000,),
        target_path="app/models.py",
    )
    assert built.dropped_files == ()
    assert built.failure_chars_dropped == 0
    assert "y" * 100 in built.text


def test_build_repair_prompt_trims_failure_text_before_dropping_files() -> None:
    """Failure output is diagnostic and highly redundant; a related file is context the
    model may actually need. Trim order matters, so it is pinned here."""
    built = build_repair_prompt(
        {"app/models.py": "x = 1\n", "app/base.py": "y = 2\n"},
        ("f" * 40_000,),
        target_path="app/models.py",
        budget=PromptBudget(max_prompt_tokens=2_000, max_failure_tokens=100),
    )
    assert built.failure_chars_dropped > 0
    assert built.dropped_files == ()  # the small related file still fit
    assert "app/base.py" in built.text


def test_build_repair_prompt_drops_related_files_but_never_the_target() -> None:
    """The model is asked to emit a corrected version of the target (D25), so a truncated
    or missing target would mean silently rewriting a truncated file."""
    built = build_repair_prompt(
        {"app/models.py": "target = 1\n", "app/big.py": "z" * 200_000},
        ("short failure",),
        target_path="app/models.py",
        budget=PromptBudget(max_prompt_tokens=1_000, max_failure_tokens=200),
    )
    assert built.dropped_files == ("app/big.py",)
    assert "app/models.py" in built.text
    assert "target = 1" in built.text
    assert "z" * 100 not in built.text


def test_build_repair_prompt_drops_lowest_ranked_related_file_first() -> None:
    """Retrieval returns related files ranked, so the last is the weakest candidate."""
    built = build_repair_prompt(
        {
            "app/models.py": "target = 1\n",
            "app/strong.py": "s" * 3_000,
            "app/weak.py": "w" * 3_000,
        },
        ("short failure",),
        target_path="app/models.py",
        budget=PromptBudget(max_prompt_tokens=1_000, max_failure_tokens=200),
    )
    assert built.dropped_files[0] == "app/weak.py"


def test_target_exceeds_budget_flags_a_target_that_cannot_ever_fit() -> None:
    budget = PromptBudget(max_prompt_tokens=1_000, max_failure_tokens=200)
    assert target_exceeds_budget("z" * 200_000, budget) is True
    assert target_exceeds_budget("x = 1\n", budget) is False


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


# --- traceback-chain context (docs/decisions.md D85) ---------------------------------

_IMPORT_CHAIN_TRACEBACK = """\
ImportError while loading conftest '/repo/tests/conftest.py'.
tests/conftest.py:19: in <module>
    from pkg.argparse import actions
src/pkg/__init__.py:12: in <module>
    from pkg.argparse import ArgumentParser
src/pkg/parsers/boolean.py:20: in <module>
    from pkg import utils
src/pkg/utils/arguments.py:12: in <module>
    def name(field: pydantic.fields.ModelField) -> str:
E   AttributeError: module 'pydantic' has no attribute 'fields'\
"""


def _write(root: Path, rel: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text("x = 1\n")


def test_files_in_traceback_returns_the_chain_nearest_error_first(tmp_path: Path) -> None:
    for rel in (
        "tests/conftest.py",
        "src/pkg/__init__.py",
        "src/pkg/parsers/boolean.py",
        "src/pkg/utils/arguments.py",
    ):
        _write(tmp_path, rel)

    found = files_in_traceback((_IMPORT_CHAIN_TRACEBACK,), tmp_path)

    # nearest-the-error first, so PromptBudget drops the least relevant if it must
    assert found[0] == "src/pkg/utils/arguments.py"
    assert "src/pkg/parsers/boolean.py" in found
    assert "src/pkg/__init__.py" in found
    assert "tests/conftest.py" not in found  # I1: never hand the agent a test file


def test_files_in_traceback_excludes_the_target_and_missing_files(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/utils/arguments.py")  # the only one that exists on disk

    found = files_in_traceback(
        (_IMPORT_CHAIN_TRACEBACK,), tmp_path, exclude_path="src/pkg/utils/arguments.py"
    )

    assert found == ()  # target excluded; the rest are not real files here


def test_files_in_traceback_is_empty_when_no_frames_match(tmp_path: Path) -> None:
    assert files_in_traceback(("some assertion failure, no paths",), tmp_path) == ()
