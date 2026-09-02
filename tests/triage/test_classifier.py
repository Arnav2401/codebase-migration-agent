from pmigrate.triage.classifier import RuleBasedClassifier
from pmigrate.types import BaselineResult, FailureClass, TestOutcome, TestRun


def _baseline(**overrides: frozenset[str]) -> BaselineResult:
    base = dict(
        passed=frozenset(),
        failed=frozenset(),
        skipped=frozenset(),
        flaky=frozenset(),
        duration_s=1.0,
    )
    base.update(overrides)
    return BaselineResult(**base)  # type: ignore[arg-type]


def test_classify_end_to_end_against_a_real_shaped_run() -> None:
    # mirrors the actual madkote/fastapi-plugins run this session (docs/decisions.md
    # D19/D20/D26): one collection error (missing dependency), one failing test with a
    # real ValidationError, and one node that already failed at baseline.
    run = TestRun(
        outcomes=(
            TestOutcome(
                node_id="tests/test_redis.py::test_connect",
                status="failed",
                duration_s=0.1,
                message="ValidationError",
                traceback=(
                    "E   pydantic_core._pydantic_core.ValidationError: "
                    "5 validation errors for RedisSettings"
                ),
                captured_stdout=None,
            ),
            TestOutcome(
                node_id="tests/test_scheduler.py::test_endpoints",
                status="failed",
                duration_s=0.1,
                message="preexisting",
                traceback="E   AssertionError: this test never worked, even at baseline",
                captured_stdout=None,
            ),
        ),
        collection_errors=("E   ModuleNotFoundError: No module named 'aiomcache'",),
        exit_code=1,
        duration_s=1.0,
        truncated=False,
    )
    baseline = _baseline(failed=frozenset({"tests/test_scheduler.py::test_endpoints"}))

    diagnoses = RuleBasedClassifier().classify(run, baseline)

    classes = {d.cls for d in diagnoses}
    assert FailureClass.VALIDATION_BEHAVIOUR in classes
    assert FailureClass.THIRD_PARTY_PIN in classes
    assert FailureClass.PREEXISTING in classes
    assert len(diagnoses) == 3  # three distinct problems, none merged incorrectly


def test_classify_with_no_baseline_still_works() -> None:
    run = TestRun(
        outcomes=(),
        collection_errors=("E   pydantic.errors.PydanticImportError: x",),
        exit_code=1,
        duration_s=1.0,
        truncated=False,
    )
    diagnoses = RuleBasedClassifier().classify(run, None)
    assert len(diagnoses) == 1
    assert diagnoses[0].cls == FailureClass.IMPORT_ERROR


def test_classify_passing_run_produces_no_diagnoses() -> None:
    run = TestRun(
        outcomes=(TestOutcome("t.py::test_a", "passed", 0.1, None, None, None),),
        collection_errors=(),
        exit_code=0,
        duration_s=1.0,
        truncated=False,
    )
    assert RuleBasedClassifier().classify(run, _baseline()) == []
