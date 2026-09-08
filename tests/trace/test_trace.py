import json
from pathlib import Path

import pytest

from pmigrate.trace import TraceEvent, TraceWriter, load_events, redact, replay_timeline


def test_redact_strips_every_provider_key_shape() -> None:
    """Each pattern is a key format this project has actually held (docs/decisions.md D90).
    A value-level allowlist would miss these, because the real leak was a key inside a URL
    inside a 429 error MESSAGE, not a field called `api_key`."""
    payload = {
        "gemini_url": "https://x/v1beta/models/g:generateContent?key=AQ.Ab8RN6KBpQh_vPPQ5mpqF",
        "groq": "Bearer gsk_abcdefghijklmnop",
        "openai": "sk-proj-abcdefghijklmnop",
        "nvidia": "nvapi-abcdefghijklmnop",
        "github": "ghp_abcdefghijklmnopqrst",
        "nested": ["AIzaSyAbcdefghijklmnop", {"deep": "api_key=supersecretvalue"}],
    }
    out = redact(payload)
    flat = json.dumps(out)
    for leak in (
        "AQ.Ab8RN6",
        "gsk_abcdef",
        "sk-proj-abcdef",
        "nvapi-abcdef",
        "ghp_abcdef",
        "AIzaSyAbc",
    ):
        assert leak not in flat, f"{leak} survived redaction"
    assert "[REDACTED]" in flat


def test_redact_rewrites_the_home_directory_but_keeps_the_path() -> None:
    """Phase 6 forbids absolute paths containing the username, not paths as such -- the
    path is the useful part for debugging."""
    out = redact({"p": f"{Path.home()}/Documents/project/x.py"})
    assert out["p"] == "~/Documents/project/x.py"


def test_writer_appends_and_reader_round_trips(tmp_path: Path) -> None:
    w = TraceWriter("run-1", trace_root=tmp_path)
    w.emit("phase", {"name": "start"})
    w.emit("llm_call", {"model": "m", "purpose": "repair"}, tokens_in=10, tokens_out=5, usd=0.01)

    events = load_events("run-1", trace_root=tmp_path)
    assert [e.kind for e in events] == ["phase", "llm_call"]
    assert events[1].usd == 0.01


def test_replay_reconstructs_cost_and_decisions_from_events_alone(tmp_path: Path) -> None:
    """phase-6-trace-pr.md's completeness test: the summary is built from the trace only."""
    w = TraceWriter("run-2", trace_root=tmp_path)
    w.emit("phase", {"name": "checkout"})
    w.emit("test_run", {"passed": 0, "total": 10, "iteration": 1})
    w.emit("llm_call", {"model": "m", "purpose": "repair"}, tokens_in=100, tokens_out=20, usd=0.02)
    w.emit("patch", {"outcome": "applied", "files_changed": ["a.py"], "source": "T2"})
    w.emit("test_run", {"passed": 7, "total": 10, "iteration": 2})

    s = replay_timeline(load_events("run-2", trace_root=tmp_path))
    assert s.llm_calls == 1
    assert s.tokens_in == 100 and s.tokens_out == 20
    assert s.usd == pytest.approx(0.02)
    assert s.usd_events_missing_cost == 0
    assert len(s.decisions) == 5
    rendered = s.render()
    assert "[patch] applied" in rendered
    assert "passed=7/10" in rendered


def test_replay_flags_unpriced_llm_calls_instead_of_counting_them_as_zero(tmp_path: Path) -> None:
    """Phase 6 requires cost accounting to match the provider's billing. An LLM call with
    no usd must not silently total as $0.00 -- the number would still look plausible."""
    w = TraceWriter("run-3", trace_root=tmp_path)
    w.emit("llm_call", {"model": "m"}, tokens_in=1, tokens_out=1)  # no usd
    w.emit("llm_call", {"model": "m"}, tokens_in=1, tokens_out=1, usd=0.05)

    s = replay_timeline(load_events("run-3", trace_root=tmp_path))
    assert s.usd_events_missing_cost == 1
    assert "LOWER BOUND" in s.render()


def test_emit_json_safe_never_kills_the_run_it_is_observing(tmp_path: Path) -> None:
    w = TraceWriter("run-4", trace_root=tmp_path)
    w.emit_json_safe("triage", {"classes": ["x"], "path": Path("/tmp/a.py")})
    assert load_events("run-4", trace_root=tmp_path)[0].payload["path"]


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown trace kind"):
        TraceEvent(run_id="r", span_id="s", parent_span=None, ts=0.0, kind="bogus")  # type: ignore[arg-type]


def test_missing_trace_raises_rather_than_returning_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no trace for run_id"):
        load_events("absent", trace_root=tmp_path)
