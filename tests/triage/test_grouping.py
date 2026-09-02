from pmigrate.triage.collect import RawFailure
from pmigrate.triage.grouping import classify_and_group, group_raw_failures
from pmigrate.types import BaselineResult, FailureClass


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


def test_preexisting_checked_before_any_text_based_rule() -> None:
    # a node in baseline.failed is PREEXISTING regardless of what its failure text says —
    # even text that would otherwise match a real rule must not override this.
    failure = RawFailure(
        node_id="tests/test_x.py::test_a",
        text="E   pydantic_core._pydantic_core.ValidationError: 1 validation error",
    )
    baseline = _baseline(failed=frozenset({"tests/test_x.py::test_a"}))
    diagnoses = classify_and_group((failure,), baseline)
    assert len(diagnoses) == 1
    assert diagnoses[0].cls == FailureClass.PREEXISTING
    assert diagnoses[0].confidence == 1.0


def test_a_collection_error_has_no_node_id_and_cannot_be_preexisting() -> None:
    failure = RawFailure(node_id=None, text="E   ModuleNotFoundError: No module named 'aiomcache'")
    diagnoses = classify_and_group((failure,), _baseline())
    assert len(diagnoses) == 1
    assert diagnoses[0].cls == FailureClass.THIRD_PARTY_PIN
    assert diagnoses[0].node_ids == ()  # no node_id to record


def test_no_baseline_means_nothing_can_be_classified_preexisting() -> None:
    failure = RawFailure(node_id="tests/test_x.py::test_a", text="E   AssertionError")
    diagnoses = classify_and_group((failure,), None)
    assert diagnoses[0].cls == FailureClass.UNKNOWN  # not PREEXISTING — no baseline to check


def test_two_failures_sharing_class_and_root_frame_are_grouped_into_one_diagnosis() -> None:
    # the exact real shape this exists for (docs/phase-4-triage.md): twenty tests failing
    # from one bad import is ONE problem, not twenty.
    shared_traceback = (
        "fastapi_plugins/settings.py:57: in ConfigManager\n"
        "    def register(self, name: str, config: pydantic.BaseSettings) -> None:\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    failures = (
        RawFailure(node_id="tests/test_control.py::test_a", text=shared_traceback),
        RawFailure(node_id="tests/test_logger.py::test_b", text=shared_traceback),
    )
    diagnoses = classify_and_group(failures, _baseline())
    assert len(diagnoses) == 1
    assert diagnoses[0].cls == FailureClass.IMPORT_ERROR
    assert set(diagnoses[0].node_ids) == {
        "tests/test_control.py::test_a",
        "tests/test_logger.py::test_b",
    }


def test_same_class_different_root_frame_stays_separate() -> None:
    text_a = "app/a.py:1: in <module>\nE   pydantic.errors.PydanticImportError: x"
    text_b = "app/b.py:1: in <module>\nE   pydantic.errors.PydanticImportError: x"
    failures = (
        RawFailure(node_id="t.py::test_a", text=text_a),
        RawFailure(node_id="t.py::test_b", text=text_b),
    )
    diagnoses = classify_and_group(failures, _baseline())
    assert len(diagnoses) == 2


def test_suspect_symbols_is_empty_pending_graph_wiring() -> None:
    failure = RawFailure(node_id="t.py::test_a", text="E   AssertionError")
    diagnoses = classify_and_group((failure,), _baseline())
    assert diagnoses[0].suspect_symbols == ()


def test_classify_and_group_is_a_thin_wrapper_over_group_raw_failures() -> None:
    # docs/decisions.md D38: classify_and_group must keep returning exactly what
    # Classifier.classify() documents (list[Diagnosis]) even after group_raw_failures
    # became the real implementation underneath it.
    failure = RawFailure(node_id="t.py::test_a", text="E   AssertionError")
    diagnoses = classify_and_group((failure,), _baseline())
    grouped = group_raw_failures((failure,), _baseline())
    assert diagnoses == [g.diagnosis for g in grouped]


def test_group_raw_failures_keeps_the_full_raw_failures_behind_each_diagnosis() -> None:
    # agent/graph.py's repair() needs the FULL multi-line traceback text to find a target
    # file (Diagnosis.evidence alone is a ~200-char snippet, nowhere near enough) — this is
    # exactly why GroupedDiagnosis exists as a separate, richer return type.
    shared_traceback = (
        "fastapi_plugins/settings.py:57: in ConfigManager\n"
        "    def register(self, name: str, config: pydantic.BaseSettings) -> None:\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    failures = (
        RawFailure(node_id="tests/test_control.py::test_a", text=shared_traceback),
        RawFailure(node_id="tests/test_logger.py::test_b", text=shared_traceback),
    )
    grouped = group_raw_failures(failures, _baseline())
    assert len(grouped) == 1
    assert grouped[0].diagnosis.cls == FailureClass.IMPORT_ERROR
    assert set(f.node_id for f in grouped[0].raw_failures) == {
        "tests/test_control.py::test_a",
        "tests/test_logger.py::test_b",
    }
    assert all(f.text == shared_traceback for f in grouped[0].raw_failures)
