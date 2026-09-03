"""Phase 5's resumable result store (docs/decisions.md D63, docs/phase-5-eval.md,
interfaces.md §8): SQLite keyed by `(repo_id, config_hash, corpus_sha)` so a re-run of
`eval/harness.py`'s `run_corpus` skips cells already scored under the exact same config
and corpus content -- mirrors interfaces.md §7's own "JSONL + SQLite index" shape for
Phase 6's (not-yet-built) trace store.

`RepoResult` (eval/metrics.py) nests an `EvalConfig` (via its own `to_dict`/`from_dict`,
eval/config.py), a `Counter[FailureClass]`, and a `tuple[ScoredRepairAttempt, ...]`
(itself wrapping a `RepairAttempt`) -- none of that is JSON-native, so this module
serializes the rest explicitly field-by-field rather than reaching for a generic
recursive serializer (`dataclasses.asdict` would leave the `Counter` un-JSON-able as-is).
Matches this codebase's existing style of explicit dataclass construction (e.g.
`eval/metrics.py`'s own `score_run`) over generic reflection-based (de)serialization.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pmigrate.agent.state import RepairAttempt
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult, ScoredRepairAttempt
from pmigrate.types import FailureClass


def config_hash(config: EvalConfig) -> str:
    """Stable across process restarts and machines -- unlike Python's builtin `hash()`,
    which salts str/frozenset hashing per-process by default (PYTHONHASHSEED), making it
    useless as a durable SQLite key. sha256 over a canonical (sorted-keys) JSON encoding
    of every field that actually varies behavior."""
    canonical = json.dumps(config.to_dict(), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def corpus_sha(manifest_path: Path) -> str:
    """sha256 of corpus/manifest.json's raw bytes -- phase-5-eval.md's "corpus sha256,"
    pinning exactly which corpus a stored result was scored against. A resume check
    against a manifest that has since changed (a repo added/dropped/re-baselined) will
    correctly miss every existing row rather than silently reusing stale results."""
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _repair_attempt_to_dict(attempt: RepairAttempt) -> dict[str, Any]:
    return {
        "iteration": attempt.iteration,
        "cls": attempt.cls.value if attempt.cls is not None else None,
        "strategy": attempt.strategy,
        "node_ids": list(attempt.node_ids),
        "outcome": attempt.outcome,
        "usd_cost": attempt.usd_cost,
    }


def _repair_attempt_from_dict(data: dict[str, Any]) -> RepairAttempt:
    return RepairAttempt(
        iteration=data["iteration"],
        cls=FailureClass(data["cls"]) if data["cls"] is not None else None,
        strategy=data["strategy"],
        node_ids=tuple(data["node_ids"]),
        outcome=data["outcome"],
        usd_cost=data["usd_cost"],
    )


def _scored_repair_to_dict(scored: ScoredRepairAttempt) -> dict[str, Any]:
    return {"attempt": _repair_attempt_to_dict(scored.attempt), "fixed": scored.fixed}


def _scored_repair_from_dict(data: dict[str, Any]) -> ScoredRepairAttempt:
    return ScoredRepairAttempt(
        attempt=_repair_attempt_from_dict(data["attempt"]), fixed=data["fixed"]
    )


def _result_to_dict(result: RepoResult) -> dict[str, Any]:
    return {
        "repo_id": result.repo_id,
        "config": result.config.to_dict(),
        "pass_rate": result.pass_rate,
        "full_green": result.full_green,
        "iterations": result.iterations,
        "usd_spent": result.usd_spent,
        "wallclock_s": result.wallclock_s,
        "final_diagnosis_counts": {
            cls.value: count for cls, count in result.final_diagnosis_counts.items()
        },
        "avg_failures_per_diagnosis": result.avg_failures_per_diagnosis,
        "scored_repairs": [_scored_repair_to_dict(s) for s in result.scored_repairs],
        "diff_line_jaccard": result.diff_line_jaccard,
        "symbol_precision": result.symbol_precision,
        "symbol_recall": result.symbol_recall,
        "trace_path": result.trace_path,
    }


def _result_from_dict(data: dict[str, Any]) -> RepoResult:
    return RepoResult(
        repo_id=data["repo_id"],
        config=EvalConfig.from_dict(data["config"]),
        pass_rate=data["pass_rate"],
        full_green=data["full_green"],
        iterations=data["iterations"],
        usd_spent=data["usd_spent"],
        wallclock_s=data["wallclock_s"],
        final_diagnosis_counts=Counter(
            {FailureClass(cls): count for cls, count in data["final_diagnosis_counts"].items()}
        ),
        avg_failures_per_diagnosis=data["avg_failures_per_diagnosis"],
        scored_repairs=tuple(_scored_repair_from_dict(s) for s in data["scored_repairs"]),
        diff_line_jaccard=data["diff_line_jaccard"],
        symbol_precision=data["symbol_precision"],
        symbol_recall=data["symbol_recall"],
        trace_path=data["trace_path"],
    )


class ResultStore:
    """One SQLite file, one table. `INSERT OR REPLACE` on `save_result` -- re-scoring an
    existing cell (an intentional single-repo redo, not `run_corpus`'s own resume path,
    which checks `has_result` first and never re-saves a cell it skipped) overwrites
    cleanly rather than raising on the primary key. `pass_rate`/`full_green`/`usd_spent`
    are denormalized into their own columns alongside the full `result_json` blob so the
    DB is queryable (`sqlite3 results.db "select repo_id, pass_rate from results ..."`)
    without deserializing JSON -- interfaces.md §7's own "SQLite index for the dashboard"
    precedent, applied here to Phase 5's result store instead of Phase 6's trace store."""

    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                repo_id TEXT NOT NULL,
                config_hash TEXT NOT NULL,
                corpus_sha TEXT NOT NULL,
                config_name TEXT NOT NULL,
                pass_rate REAL NOT NULL,
                full_green INTEGER NOT NULL,
                usd_spent REAL NOT NULL,
                result_json TEXT NOT NULL,
                written_at REAL NOT NULL,
                PRIMARY KEY (repo_id, config_hash, corpus_sha)
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def has_result(self, repo_id: str, config_hash: str, corpus_sha: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM results WHERE repo_id = ? AND config_hash = ? AND corpus_sha = ?",
            (repo_id, config_hash, corpus_sha),
        ).fetchone()
        return row is not None

    def load_result(self, repo_id: str, config_hash: str, corpus_sha: str) -> RepoResult | None:
        row = self._conn.execute(
            "SELECT result_json FROM results "
            "WHERE repo_id = ? AND config_hash = ? AND corpus_sha = ?",
            (repo_id, config_hash, corpus_sha),
        ).fetchone()
        if row is None:
            return None
        return _result_from_dict(json.loads(row[0]))

    def save_result(self, result: RepoResult, corpus_sha: str, *, written_at: float) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO results
                (repo_id, config_hash, corpus_sha, config_name, pass_rate, full_green,
                 usd_spent, result_json, written_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.repo_id,
                config_hash(result.config),
                corpus_sha,
                result.config.name,
                result.pass_rate,
                int(result.full_green),
                result.usd_spent,
                json.dumps(_result_to_dict(result)),
                written_at,
            ),
        )
        self._conn.commit()


@dataclass(frozen=True)
class ResumeContext:
    """Bundles what `run_corpus` needs to skip already-scored cells -- `store` and
    `corpus_sha` always travel together (a store with no corpus_sha to key against, or a
    corpus_sha with no store to check it against, is meaningless), so one optional param
    on `run_corpus` beats two that would have to agree independently."""

    store: ResultStore
    corpus_sha: str
