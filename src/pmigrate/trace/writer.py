"""JSONL writer plus the redaction rules Phase 6 requires.

One file per run under `trace_root/<run_id>.jsonl`, appended as events happen rather than
buffered to the end: a run that dies to a rate limit or a killed container is exactly the
run whose trace you want, and this project has produced plenty of those.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from pmigrate.trace.events import TraceEvent, TraceKind

DEFAULT_TRACE_ROOT = Path("traces")

# Anything shaped like a provider key. Checked against the real key formats this project
# uses: Gemini `AQ.<...>`/`AIza<...>`, Groq `gsk_<...>`, OpenAI `sk-<...>`, NVIDIA `nvapi-<...>`,
# GitHub `gh[pousr]_<...>`. Applied to serialized payload text, not just string values, so a
# key buried inside a nested structure or an error message is still caught.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAQ\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bgsk_[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bnvapi-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{10,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[=:]\s*\S+"),
)

_REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Strips secrets and the developer's home directory from anything bound for the trace.

    Phase 6 names three things that must not land here: API keys, absolute paths containing
    the username, and full repo contents. This handles the first two; the third is a caller
    obligation (store a hash and a path, not the file) because only the caller knows which
    payload field is a file body.

    Home-directory paths are rewritten to `~/...` rather than dropped: the path is genuinely
    useful for debugging, it is only the username that must not ship. Found the hard way in
    this project's own logs, where a Gemini key appeared in full inside a 429 error message
    (the URL carried `?key=`), which is exactly the case a value-level allowlist would miss
    and a text-level scrub catches.
    """
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    out = value
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    home = str(Path.home())
    if home in out:
        out = out.replace(home, "~")
    return out


class TraceWriter:
    """Append-only JSONL for one run. Thread-safe because `run_corpus` runs repos
    concurrently (D66) and a Python-level write is not one atomic OS write -- the same
    reasoning behind `_failures_out_lock` in eval/harness.py."""

    def __init__(self, run_id: str, *, trace_root: Path = DEFAULT_TRACE_ROOT) -> None:
        self.run_id = run_id
        self.path = trace_root / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(
        self,
        kind: TraceKind,
        payload: dict[str, Any] | None = None,
        *,
        parent_span: str | None = None,
        span_id: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        usd: float | None = None,
        ts: float | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            run_id=self.run_id,
            span_id=span_id or uuid.uuid4().hex[:12],
            parent_span=parent_span,
            ts=time.time() if ts is None else ts,
            kind=kind,
            payload=redact(payload or {}),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            usd=usd,
        )
        line = event.to_json()
        with self._lock, self.path.open("a") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # a killed container must not lose the event that explains why
        return event

    def emit_json_safe(self, kind: TraceKind, payload: dict[str, Any]) -> TraceEvent:
        """`emit` for payloads that may contain non-JSON-serializable values (dataclasses,
        Paths, Counters). Stringifies whatever `json` refuses rather than raising: a trace
        write must never be the thing that kills a run it was only observing."""
        try:
            json.dumps(payload)
        except TypeError:
            payload = {k: (v if _json_ok(v) else repr(v)) for k, v in payload.items()}
        return self.emit(kind, payload)


def _json_ok(value: Any) -> bool:
    try:
        json.dumps(value)
    except TypeError:
        return False
    return True
