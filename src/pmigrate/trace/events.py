"""The event type itself (docs/interfaces.md §7), kept in its own module so `writer` and
`reader` can both depend on it without importing each other."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

TraceKind = Literal["phase", "llm_call", "tool_call", "patch", "test_run", "triage", "error"]

_KINDS: frozenset[str] = frozenset(
    ("phase", "llm_call", "tool_call", "patch", "test_run", "triage", "error")
)


@dataclass(frozen=True)
class TraceEvent:
    """One thing that happened, as specified in docs/interfaces.md §7.

    `tokens_in`/`tokens_out`/`usd` are `None` rather than 0 for non-LLM events, keeping
    "this event had no cost" distinguishable from "this event cost nothing measurable" --
    the same reasoning D57 applied to `RepoResult`'s optional metrics, and it matters here
    because Phase 6's acceptance criterion is that cost accounting matches the provider's
    billing. Summing `None` as 0 would silently hide a call whose usage never got recorded.
    """

    run_id: str
    span_id: str
    parent_span: str | None
    ts: float
    kind: TraceKind
    payload: dict[str, Any] = field(default_factory=dict)
    tokens_in: int | None = None
    tokens_out: int | None = None
    usd: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(
                f"unknown trace kind {self.kind!r} -- expected one of {sorted(_KINDS)}"
            )

    def to_json(self) -> str:
        return json.dumps(
            {
                "run_id": self.run_id,
                "span_id": self.span_id,
                "parent_span": self.parent_span,
                "ts": self.ts,
                "kind": self.kind,
                "payload": self.payload,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "usd": self.usd,
            },
            sort_keys=True,
        )

    @staticmethod
    def from_json(line: str) -> TraceEvent:
        d = json.loads(line)
        return TraceEvent(
            run_id=d["run_id"],
            span_id=d["span_id"],
            parent_span=d["parent_span"],
            ts=d["ts"],
            kind=d["kind"],
            payload=d.get("payload", {}),
            tokens_in=d.get("tokens_in"),
            tokens_out=d.get("tokens_out"),
            usd=d.get("usd"),
        )
