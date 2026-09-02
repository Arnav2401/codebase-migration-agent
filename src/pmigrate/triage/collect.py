"""Turns a `TestRun` into individually-classifiable failures. `agent/repair.py`'s
`collect_failure_texts` needs the same underlying data (every failing outcome's
traceback+message, plus every collection error) but only as one flat blob for a single
repair prompt; triage needs to classify each failure separately before grouping. Built
here, once, and reused by `repair.py` rather than re-derived — the D31 lesson applied
before a second copy could drift, not after.
"""

from __future__ import annotations

from dataclasses import dataclass

from pmigrate.types import TestRun


@dataclass(frozen=True)
class RawFailure:
    node_id: str | None  # None for a collection error — not tied to one specific test
    text: str


def collect_raw_failures(run: TestRun) -> tuple[RawFailure, ...]:
    """Every failing outcome and collection error in `run`, each kept separate (unlike
    `agent/repair.py`'s `collect_failure_texts`, which flattens everything into one
    blob). Collection errors are NOT `TestOutcome`s at all (results.py keeps them
    separate) but they block whole files from even running, which makes them at least
    as valuable a triage target as a single already-collected failing test."""
    failures = [
        RawFailure(node_id=o.node_id, text=f"{o.traceback or ''}\n{o.message or ''}")
        for o in run.outcomes
        if o.status in ("failed", "error")
    ]
    failures.extend(RawFailure(node_id=None, text=e) for e in run.collection_errors)
    return tuple(failures)
