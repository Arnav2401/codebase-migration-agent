from pmigrate.triage.rules import classify_text
from pmigrate.types import FailureClass

# every text below is the exact real failure shape found against a real corpus repo this
# session (docs/decisions.md D19/D20/D26/D35) — not invented, per rules.py's own module
# docstring on why only classes with real evidence get a rule.

_IMPORT_ERROR_TEXT = (
    "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved to the "
    "`pydantic-settings` package. See https://docs.pydantic.dev/2.13/migration/"
    "#basesettings-has-moved-to-pydantic-settings for more details."
)

_THIRD_PARTY_PIN_TEXT = (
    "fastapi_plugins/memcached.py:10: in <module>\n"
    "    import aiomcache\n"
    "E   ModuleNotFoundError: No module named 'aiomcache'"
)

_VALIDATION_BEHAVIOUR_TEXT = (
    "tests/test_redis.py:35: in <module>\n"
    "    fastapi_plugins.RedisSettings(redis_url='redis://localhost:6379/1')\n"
    "E   pydantic_core._pydantic_core.ValidationError: 5 validation errors for RedisSettings\n"
    "E   redis_user\n"
    "E     Input should be a valid string [type=string_type, input_value=None, "
    "input_type=NoneType]"
)


def test_classifies_pydantic_import_error() -> None:
    rule = classify_text(_IMPORT_ERROR_TEXT)
    assert rule is not None
    assert rule.cls == FailureClass.IMPORT_ERROR
    assert rule.strategy == "fix_import"


def test_classifies_cannot_import_name_variant() -> None:
    text = "E   ImportError: cannot import name 'BaseSettings' from 'pydantic'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.IMPORT_ERROR


def test_classifies_third_party_pin_excluding_pydantic_family() -> None:
    rule = classify_text(_THIRD_PARTY_PIN_TEXT)
    assert rule is not None
    assert rule.cls == FailureClass.THIRD_PARTY_PIN
    assert rule.strategy == "pin_dependency"


def test_missing_pydantic_settings_module_is_not_third_party_pin() -> None:
    # a missing pydantic-family module is a T1/sandbox coverage gap (extra_packages() in
    # sandbox/image.py should already prevent this), not "someone else's dependency" —
    # docs/decisions.md D20 built the fix for exactly this case.
    text = "E   ModuleNotFoundError: No module named 'pydantic_settings'"
    rule = classify_text(text)
    assert rule is None  # falls to UNKNOWN, not misfiled as THIRD_PARTY_PIN


def test_classifies_validation_behaviour() -> None:
    rule = classify_text(_VALIDATION_BEHAVIOUR_TEXT)
    assert rule is not None
    assert rule.cls == FailureClass.VALIDATION_BEHAVIOUR
    assert rule.strategy == "semantic_repair"


def test_classifies_class_def_error() -> None:
    text = "E   pydantic.errors.PydanticUserError: Validators cannot be used with default_factory"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.CLASS_DEF_ERROR


def test_classifies_removed_api() -> None:
    text = "E   AttributeError: 'Foo' object has no attribute 'dict'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.REMOVED_API
    assert rule.strategy == "missing_t1_rule"


def test_returns_none_for_unrecognized_text() -> None:
    assert classify_text("E   AssertionError: assert 1 == 2") is None
