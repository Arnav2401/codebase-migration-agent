"""Reading a trace back, and the replay that Phase 6 uses as its completeness test.

phase-6-trace-pr.md: "a run can be replayed from its trace. If you can't replay it, the
trace is incomplete." `replay_timeline` is deliberately built from the events ALONE -- it
never touches `eval_results.db`, the overlay, or the corpus manifest -- so a gap in the
trace shows up as a gap in the replay instead of being quietly filled in from elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pmigrate.trace.events import TraceEvent
from pmigrate.trace.writer import DEFAULT_TRACE_ROOT


def load_events(run_id: str, *, trace_root: Path = DEFAULT_TRACE_ROOT) -> list[TraceEvent]:
    """Events in the order they were written. Not re-sorted by `ts`: the file order is the
    causal order, and wall-clock timestamps from concurrent repos (D66) can interleave in
    ways that would reorder a parent after its own child."""
    path = trace_root / f"{run_id}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"no trace for run_id {run_id!r} at {path}")
    return [TraceEvent.from_json(line) for line in path.read_text().splitlines() if line.strip()]


@dataclass(frozen=True)
class ReplaySummary:
    """What a run did, reconstructed from its trace alone."""

    run_id: str
    n_events: int
    kinds: dict[str, int]
    llm_calls: int
    tokens_in: int
    tokens_out: int
    usd: float
    usd_events_missing_cost: int
    decisions: list[str]

    def render(self) -> str:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(self.kinds.items()))
        lines = [
            f"run_id: {self.run_id}",
            f"events: {self.n_events}  ({breakdown})",
            f"llm calls: {self.llm_calls}  tokens in/out: {self.tokens_in}/{self.tokens_out}",
            f"cost: ${self.usd:.4f}",
        ]
        if self.usd_events_missing_cost:
            # I6 is about reconstructibility, so an unpriced LLM call is surfaced rather
            # than folded into the total as a zero -- the total would still look plausible.
            lines.append(
                f"WARNING: {self.usd_events_missing_cost} llm_call event(s) carried no usd; "
                "the cost above is a LOWER BOUND, not the run's true spend"
            )
        lines.append("")
        lines.append("decision sequence:")
        lines.extend(f"  {i:3d}. {d}" for i, d in enumerate(self.decisions, 1))
        return "\n".join(lines)


def replay_timeline(events: list[TraceEvent]) -> ReplaySummary:
    """Reconstructs the run's decision sequence and cost from events alone."""
    if not events:
        raise ValueError("cannot replay an empty trace")

    kinds: dict[str, int] = {}
    tokens_in = tokens_out = 0
    usd = 0.0
    llm_calls = 0
    missing_cost = 0
    decisions: list[str] = []

    for e in events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
        tokens_in += e.tokens_in or 0
        tokens_out += e.tokens_out or 0
        if e.kind == "llm_call":
            llm_calls += 1
            if e.usd is None:
                missing_cost += 1
        usd += e.usd or 0.0
        decisions.append(_describe(e))

    return ReplaySummary(
        run_id=events[0].run_id,
        n_events=len(events),
        kinds=kinds,
        llm_calls=llm_calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        usd=usd,
        usd_events_missing_cost=missing_cost,
        decisions=decisions,
    )


def _describe(e: TraceEvent) -> str:
    """One human-readable line per event. Reads the payload defensively -- a trace from an
    older schema must still replay, or the trace stops being an audit record the moment the
    code moves on."""
    p = e.payload
    if e.kind == "phase":
        return f"[phase] {p.get('name', '?')} {p.get('detail', '')}".rstrip()
    if e.kind == "llm_call":
        cost = "unpriced" if e.usd is None else f"${e.usd:.4f}"
        return (
            f"[llm] {p.get('purpose', 'call')} model={p.get('model', '?')} "
            f"in={e.tokens_in} out={e.tokens_out} {cost}"
        )
    if e.kind == "patch":
        return (
            f"[patch] {p.get('outcome', '?')} files={p.get('files_changed', [])} "
            f"source={p.get('source', '?')}"
        )
    if e.kind == "test_run":
        return (
            f"[tests] passed={p.get('passed', '?')}/{p.get('total', '?')} "
            f"iteration={p.get('iteration', '?')}"
        )
    if e.kind == "triage":
        return f"[triage] classes={p.get('classes', [])} target={p.get('target', '-')}"
    if e.kind == "error":
        return f"[error] {p.get('where', '?')}: {p.get('message', '')}"
    return f"[{e.kind}] {p}"
