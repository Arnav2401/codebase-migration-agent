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


# docs/decisions.md D56: found live during the D55 hand-labelling pass -- the rule-based
# classifier's accuracy against 411 real hand-labelled failures was 76.9% before these four
# rules (already excluding 18 PREEXISTING mislabels the labelling tool couldn't have caught,
# since it never showed baseline data), 96.8% after. Every text below is real, from that
# corpus run, not invented.


def test_classifies_no_validator_found_runtime_error_as_class_def_error() -> None:
    # pydantic v1's OWN find_validators raises a plain RuntimeError, not PydanticUserError,
    # at class-definition time when arbitrary_types_allowed isn't set for an unknown type.
    text = (
        "E   RuntimeError: no validator found for <class 'kor.encoders.typedefs.Encoder'>, "
        "see `arbitrary_types_allowed` in Config"
    )
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.CLASS_DEF_ERROR


def test_classifies_fastapi_wrapped_response_field_error_as_class_def_error() -> None:
    # FastAPI's create_response_field wraps the underlying PydanticSchemaGenerationError in
    # its own FastAPIError -- the literal string "PydanticUserError" never appears.
    text = (
        "E           fastapi.exceptions.FastAPIError: Invalid args for response field! "
        "Hint: check that list[draco.server.models.shared.ClingoModel] is a valid "
        "Pydantic field type."
    )
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.CLASS_DEF_ERROR


def test_classifies_pydantic_module_attribute_removal_as_removed_api() -> None:
    # pydantic v2's _getattr_migration raises this for removed v1 names accessed as
    # module/type attributes (ModelField), not instance methods -- a different shape from
    # the "'X' object has no attribute 'dict'" rule above.
    text = "E   AttributeError: module 'pydantic.fields' has no attribute 'ModelField'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.REMOVED_API


def test_classifies_pydantic_has_no_attribute_fields_as_removed_api() -> None:
    text = "E   AttributeError: module 'pydantic' has no attribute 'fields'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.REMOVED_API


def test_classifies_model_copy_on_non_model_as_validation_behaviour() -> None:
    # the single biggest gap the hand-labelling pass found (45 of 411 raw failures): a
    # naive T1/T2 rewrite applies .model_copy() to a value that was never actually a
    # Pydantic model (here a plain dict).
    text = (
        ">       metadata = metadata.model_copy() if metadata is not None else {}\n"
        "E       AttributeError: 'dict' object has no attribute 'model_copy'"
    )
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.VALIDATION_BEHAVIOUR


def test_classifies_model_dump_on_non_model_as_validation_behaviour() -> None:
    text = "E   AttributeError: 'Document' object has no attribute 'model_copy'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.VALIDATION_BEHAVIOUR


def test_import_error_matches_non_pydantic_source_module() -> None:
    # docs/decisions.md D56: broadened from 'pydantic' specifically -- a repo's OWN
    # package can fail to import as a collateral symptom of a pydantic issue deeper in its
    # import chain, without the word "pydantic" appearing in the shallow ImportError text.
    text = "E   ImportError: cannot import name 'server' from 'draco'"
    rule = classify_text(text)
    assert rule is not None
    assert rule.cls == FailureClass.IMPORT_ERROR
