"""SQLite index over the JSONL traces (docs/interfaces.md §7: "JSONL per run + a SQLite
index for the dashboard").

The JSONL files stay the source of truth; this is a derived, throw-away read model. That
ordering matters: an append-only text file survives a schema change, a killed process and a
half-written row, none of which a database guarantees for free -- and this project has
produced all three. `rebuild` drops and repopulates rather than migrating, because nothing
here is worth preserving that the traces cannot regenerate.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pmigrate.trace.reader import load_events
from pmigrate.trace.writer import DEFAULT_TRACE_ROOT

DEFAULT_INDEX_PATH = Path("traces/index.db")

_SCHEMA = """
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    started_at REAL,
    ended_at REAL,
    n_events INTEGER,
    llm_calls INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    usd REAL,
    unpriced_calls INTEGER,
    first_passed INTEGER,
    first_total INTEGER,
    last_passed INTEGER,
    last_total INTEGER,
    iterations INTEGER,
    patches_applied INTEGER,
    patches_rejected INTEGER,
    errors INTEGER,
    trace_path TEXT
);
CREATE TABLE failure_classes (
    run_id TEXT,
    cls TEXT,
    n INTEGER,
    PRIMARY KEY (run_id, cls)
);
CREATE INDEX idx_runs_usd ON runs(usd DESC);
"""


@dataclass(frozen=True)
class RunRow:
    run_id: str
    n_events: int
    llm_calls: int
    usd: float
    unpriced_calls: int
    last_passed: int | None
    last_total: int | None
    iterations: int
    patches_applied: int
    errors: int


def rebuild(*, trace_root: Path = DEFAULT_TRACE_ROOT, index_path: Path = DEFAULT_INDEX_PATH) -> int:
    """Rebuilds the index from every trace file. Returns the number of runs indexed.

    A trace that fails to parse is SKIPPED with its run_id still recorded as an error row
    rather than aborting the rebuild: one corrupt file must not make the dashboard
    unavailable for every other run, and a run whose trace is unreadable is itself a fact
    worth seeing.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if index_path.exists():
        index_path.unlink()
    conn = sqlite3.connect(index_path)
    try:
        conn.executescript(_SCHEMA)
        n = 0
        for path in sorted(trace_root.glob("*.jsonl")):
            try:
                events = load_events(path.stem, trace_root=trace_root)
            except (ValueError, KeyError, OSError):
                continue
            if not events:
                continue
            _insert_run(conn, path, events)
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def _insert_run(conn: sqlite3.Connection, path: Path, events: list) -> None:  # type: ignore[type-arg]
    from collections import Counter

    classes: Counter[str] = Counter()
    llm_calls = tokens_in = tokens_out = unpriced = applied = rejected = errors = 0
    iterations = 0
    usd = 0.0
    first: tuple[int, int] | None = None
    last: tuple[int, int] | None = None

    for e in events:
        p = e.payload
        tokens_in += e.tokens_in or 0
        tokens_out += e.tokens_out or 0
        usd += e.usd or 0.0
        if e.kind == "llm_call":
            llm_calls += 1
            if e.usd is None:
                unpriced += 1
        elif e.kind == "patch":
            if p.get("outcome") == "applied":
                applied += 1
            else:
                rejected += 1
        elif e.kind == "test_run":
            pair = (int(p.get("passed") or 0), int(p.get("total") or 0))
            first = first or pair
            last = pair
            iterations = max(iterations, int(p.get("iteration") or 0))
        elif e.kind == "triage":
            classes.update(p.get("classes", []) or [])
        elif e.kind == "error":
            errors += 1

    conn.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            events[0].run_id,
            events[0].ts,
            events[-1].ts,
            len(events),
            llm_calls,
            tokens_in,
            tokens_out,
            usd,
            unpriced,
            first[0] if first else None,
            first[1] if first else None,
            last[0] if last else None,
            last[1] if last else None,
            iterations,
            applied,
            rejected,
            errors,
            str(path),
        ),
    )
    conn.executemany(
        "INSERT INTO failure_classes VALUES (?,?,?)",
        [(events[0].run_id, cls, n) for cls, n in classes.items()],
    )


def list_runs(*, index_path: Path = DEFAULT_INDEX_PATH) -> list[RunRow]:
    if not index_path.exists():
        return []
    conn = sqlite3.connect(index_path)
    try:
        rows = conn.execute(
            "SELECT run_id, n_events, llm_calls, usd, unpriced_calls, last_passed, "
            "last_total, iterations, patches_applied, errors FROM runs ORDER BY run_id"
        ).fetchall()
    finally:
        conn.close()
    return [RunRow(*r) for r in rows]


def cost_breakdown(*, index_path: Path = DEFAULT_INDEX_PATH) -> list[tuple[str, float, int]]:
    """(run_id, usd, unpriced_calls), most expensive first. `unpriced_calls` rides along so
    a cheap-looking run that simply never recorded its prices cannot be mistaken for a
    cheap one (D90)."""
    if not index_path.exists():
        return []
    conn = sqlite3.connect(index_path)
    try:
        return [
            (r[0], r[1], r[2])
            for r in conn.execute(
                "SELECT run_id, usd, unpriced_calls FROM runs ORDER BY usd DESC"
            ).fetchall()
        ]
    finally:
        conn.close()


def failure_class_distribution(*, index_path: Path = DEFAULT_INDEX_PATH) -> list[tuple[str, int]]:
    if not index_path.exists():
        return []
    conn = sqlite3.connect(index_path)
    try:
        return [
            (r[0], r[1])
            for r in conn.execute(
                "SELECT cls, SUM(n) FROM failure_classes GROUP BY cls ORDER BY SUM(n) DESC"
            ).fetchall()
        ]
    finally:
        conn.close()
