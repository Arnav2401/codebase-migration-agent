"""Parse pytest-json-report output into the structured TestRun/TestOutcome shape
(docs/interfaces.md §3). Pure and fully testable without Docker or even a real pytest
run — the JSON shapes below were captured from actual local pytest-json-report runs
(including the exact failure modes docs/phase-2-sandbox.md calls out), not guessed from
the library's docs. See test_results.py's fixtures for the literal captured JSON.

The single most important thing this module gets right (docs/phase-2-sandbox.md
"Structured results"): a pydantic v2 migration usually breaks at *import time*. Verified
locally: a collection error in ONE file, without `--continue-on-collection-errors`, aborts
pytest's entire session — `report["tests"]` comes back completely EMPTY even for files with
nothing wrong, and naive code would read that as "0 failures, success." `runner.py` always
passes `--continue-on-collection-errors`; this module additionally treats a failed
collector as a `collection_errors` entry, distinct from (and never confused with) a normal
test failure.

Also verified locally: which phase (`setup`, `call`, `teardown`) carries the crash info
differs by failure mode — a test with outcome="error" (e.g. a raising fixture) has NO
`call` key at all; the failure is under `setup`. Checking all three phases in order, rather
than assuming `call` exists, is not optional correctness here.
"""

from __future__ import annotations

from typing import Any

from pmigrate.types import TestOutcome, TestRun

_PHASES = ("setup", "call", "teardown")

# docs/phase-2-sandbox.md "Truncation": trim at capture time, never send an untrimmed log
# to a model. Numbers are a starting point — tune against real repo output once corpus
# baselines exist to measure against.
MAX_TRACEBACK_LINES = 200
MAX_STDOUT_CHARS = 4000


def _failing_phase(test: dict[str, Any]) -> dict[str, Any] | None:
    for phase_name in _PHASES:
        phase: dict[str, Any] | None = test.get(phase_name)
        if phase is not None and phase.get("outcome") in ("failed", "error"):
            return phase
    return None


def _truncate_traceback(text: str | None) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    lines = text.splitlines()
    if len(lines) <= MAX_TRACEBACK_LINES:
        return text, False
    head = lines[: MAX_TRACEBACK_LINES // 2]
    tail = lines[-(MAX_TRACEBACK_LINES // 2) :]
    omitted = len(lines) - len(head) - len(tail)
    truncated = "\n".join([*head, f"... [{omitted} lines omitted] ...", *tail])
    return truncated, True


def _truncate_stdout(text: str | None) -> tuple[str | None, bool]:
    if text is None or len(text) <= MAX_STDOUT_CHARS:
        return text, False
    half = MAX_STDOUT_CHARS // 2
    return f"{text[:half]}\n...[truncated]...\n{text[-half:]}", True


def parse_json_report(report: dict[str, Any]) -> TestRun:
    outcomes: list[TestOutcome] = []
    any_truncated = False

    for test in report.get("tests", []):
        phase = _failing_phase(test)
        message = None
        traceback_text = None
        stdout = None
        if phase is not None:
            crash = phase.get("crash")
            message = crash.get("message") if crash else None
            longrepr = phase.get("longrepr")
            traceback_text = longrepr if isinstance(longrepr, str) else None
            stdout = phase.get("stdout")

        traceback_text, tb_truncated = _truncate_traceback(traceback_text)
        stdout, stdout_truncated = _truncate_stdout(stdout)
        any_truncated = any_truncated or tb_truncated or stdout_truncated

        duration = sum(test[p]["duration"] for p in _PHASES if p in test and "duration" in test[p])

        outcomes.append(
            TestOutcome(
                node_id=test["nodeid"],
                status=test["outcome"],
                duration_s=duration,
                message=message,
                traceback=traceback_text,
                captured_stdout=stdout,
            )
        )

    collection_errors = []
    for collector in report.get("collectors", []):
        if collector.get("outcome") != "failed":
            continue
        longrepr = collector.get("longrepr")
        raw_text = longrepr if isinstance(longrepr, str) else str(longrepr)
        truncated_text, tb_truncated = _truncate_traceback(raw_text)
        any_truncated = any_truncated or tb_truncated
        collection_errors.append(truncated_text or "")

    return TestRun(
        outcomes=tuple(outcomes),
        collection_errors=tuple(collection_errors),
        exit_code=report.get("exitcode", -1),
        duration_s=report.get("duration", 0.0),
        truncated=any_truncated,
    )
