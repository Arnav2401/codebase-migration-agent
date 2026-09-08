"""Phase 6a: the audit trace (docs/interfaces.md §7, docs/phase-6-trace-pr.md).

Exists to make invariant I6 real: "every number you report is reconstructible". Every LLM
call, patch, test run and triage decision lands here with tokens and USD attached, so a
scored eval result can be explained after the fact rather than re-derived by re-running it
-- which this project has repeatedly been unable to do, because provider quota makes any
re-run a different experiment (D74).
"""

from pmigrate.trace.events import TraceEvent, TraceKind
from pmigrate.trace.reader import load_events, replay_timeline
from pmigrate.trace.writer import TraceWriter, redact

__all__ = [
    "TraceEvent",
    "TraceKind",
    "TraceWriter",
    "load_events",
    "redact",
    "replay_timeline",
]
