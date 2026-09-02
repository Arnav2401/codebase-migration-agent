"""Fixtures below are shaped exactly like real pytest-json-report output captured from
local runs (see results.py's docstring) — trimmed to the fields the parser reads, not
invented from the library's documentation.
"""

from pmigrate.sandbox.results import (
    MAX_STDOUT_CHARS,
    MAX_TRACEBACK_LINES,
    parse_json_report,
)

MIXED_REPORT = {
    "duration": 0.02,
    "exitcode": 1,
    "summary": {"passed": 1, "failed": 1, "skipped": 1, "total": 3, "collected": 3},
    "tests": [
        {
            "nodeid": "test_ok.py::test_pass",
            "outcome": "passed",
            "setup": {"duration": 0.0001, "outcome": "passed"},
            "call": {"duration": 0.0001, "outcome": "passed"},
            "teardown": {"duration": 0.0001, "outcome": "passed"},
        },
        {
            "nodeid": "test_ok.py::test_fail",
            "outcome": "failed",
            "setup": {"duration": 0.0001, "outcome": "passed"},
            "call": {
                "duration": 0.0002,
                "outcome": "failed",
                "crash": {"path": "test_ok.py", "lineno": 5, "message": "assert 1 == 2"},
                "longrepr": "def test_fail():\n>       assert 1 == 2\nE       assert 1 == 2",
            },
            "teardown": {"duration": 0.0001, "outcome": "passed"},
        },
        {
            "nodeid": "test_ok.py::test_skip",
            "outcome": "skipped",
            "setup": {
                "duration": 0.0001,
                "outcome": "skipped",
                "longrepr": "('/tmp/test_ok.py', 8, 'Skipped: demo')",
            },
            "teardown": {"duration": 0.0001, "outcome": "passed"},
        },
    ],
    "collectors": [
        {"nodeid": "", "outcome": "passed", "result": []},
        {
            "nodeid": "test_broken_import.py",
            "outcome": "failed",
            "result": [],
            "longrepr": (
                "ImportError while importing test module 'test_broken_import.py'.\n"
                "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved "
                "to the `pydantic-settings` package."
            ),
        },
        {"nodeid": "test_ok.py", "outcome": "passed", "result": []},
    ],
}

SETUP_ERROR_REPORT = {
    "duration": 0.01,
    "exitcode": 1,
    "tests": [
        {
            "nodeid": "test_error_case.py::test_uses_broken",
            "outcome": "error",
            "setup": {
                "duration": 0.0003,
                "outcome": "failed",
                "crash": {
                    "path": "test_error_case.py",
                    "lineno": 5,
                    "message": "RuntimeError: fixture blew up",
                },
                "longrepr": "def broken():\nE   RuntimeError: fixture blew up",
            },
            "teardown": {"duration": 0.0001, "outcome": "passed"},
            # deliberately NO "call" key — pytest never got there
        }
    ],
    "collectors": [],
}

COLLECTION_ABORTED_REPORT = {
    "duration": 0.05,
    "exitcode": 2,
    "tests": [],  # everything wiped out, exactly the failure mode the doc warns about
    "collectors": [
        {
            "nodeid": "test_broken_import.py",
            "outcome": "failed",
            "result": [],
            "longrepr": "ImportError while importing test module ...",
        }
    ],
}


def test_mixed_outcomes_and_collection_error_both_surface() -> None:
    run = parse_json_report(MIXED_REPORT)
    statuses = {o.node_id: o.status for o in run.outcomes}
    assert statuses == {
        "test_ok.py::test_pass": "passed",
        "test_ok.py::test_fail": "failed",
        "test_ok.py::test_skip": "skipped",
    }
    assert len(run.collection_errors) == 1
    assert "PydanticImportError" in run.collection_errors[0]
    assert run.exit_code == 1


def test_failed_test_carries_message_and_traceback() -> None:
    run = parse_json_report(MIXED_REPORT)
    failed = next(o for o in run.outcomes if o.status == "failed")
    assert failed.message == "assert 1 == 2"
    assert failed.traceback is not None and "assert 1 == 2" in failed.traceback


def test_setup_error_has_no_call_phase_but_is_still_parsed() -> None:
    # the exact case verified locally: outcome="error", failure lives under "setup",
    # there is no "call" key at all — the parser must not assume it exists.
    run = parse_json_report(SETUP_ERROR_REPORT)
    assert len(run.outcomes) == 1
    outcome = run.outcomes[0]
    assert outcome.status == "error"
    assert outcome.message == "RuntimeError: fixture blew up"
    assert outcome.traceback is not None


def test_collection_abort_does_not_look_like_zero_failures() -> None:
    # this is the failure mode docs/phase-2-sandbox.md calls "the single most common
    # failure mode of the whole project" — a wiped-out tests list must never be silently
    # read as a clean pass. collection_errors is what carries the real signal.
    run = parse_json_report(COLLECTION_ABORTED_REPORT)
    assert run.outcomes == ()
    assert len(run.collection_errors) == 1
    assert run.exit_code != 0


def test_traceback_truncation_sets_flag_and_keeps_head_and_tail() -> None:
    long_traceback = "\n".join(f"line {i}" for i in range(MAX_TRACEBACK_LINES + 50))
    report = {
        "duration": 0.0,
        "exitcode": 1,
        "tests": [
            {
                "nodeid": "t.py::test_long",
                "outcome": "failed",
                "call": {
                    "duration": 0.0,
                    "outcome": "failed",
                    "crash": {"message": "boom"},
                    "longrepr": long_traceback,
                },
            }
        ],
        "collectors": [],
    }
    run = parse_json_report(report)
    assert run.truncated is True
    tb = run.outcomes[0].traceback
    assert tb is not None
    assert "line 0" in tb
    assert f"line {MAX_TRACEBACK_LINES + 49}" in tb
    assert "omitted" in tb
    assert len(tb.splitlines()) < MAX_TRACEBACK_LINES + 50


def test_stdout_truncation() -> None:
    long_stdout = "x" * (MAX_STDOUT_CHARS * 3)
    report = {
        "duration": 0.0,
        "exitcode": 1,
        "tests": [
            {
                "nodeid": "t.py::test_noisy",
                "outcome": "failed",
                "call": {
                    "duration": 0.0,
                    "outcome": "failed",
                    "crash": {"message": "boom"},
                    "longrepr": "short",
                    "stdout": long_stdout,
                },
            }
        ],
        "collectors": [],
    }
    run = parse_json_report(report)
    assert run.truncated is True
    assert run.outcomes[0].captured_stdout is not None
    assert len(run.outcomes[0].captured_stdout) < len(long_stdout)


def test_untruncated_report_sets_flag_false() -> None:
    run = parse_json_report(MIXED_REPORT)
    assert run.truncated is False
