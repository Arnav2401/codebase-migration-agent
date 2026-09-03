"""Interactive hand-labelling tool for docs/phase-4-triage.md's classifier-accuracy
criterion (>=85% on >=100 hand-labelled real failures). Groups `triage_failures_dev.jsonl`
by the SAME key `group_raw_failures` uses -- `(predicted_cls, deepest_first_party_frame)`
-- so a human makes ~20 real judgment calls instead of ~400 near-duplicate ones; each
answer is propagated to every raw failure in that group. docs/decisions.md D55 states the
trade-off this makes explicit: it assumes every member of a group truly shares one class,
which a mis-grouped case would silently violate.

Deliberately does NOT show `predicted_cls` before asking for the true class -- revealing
the classifier's own guess first would anchor the human's judgment toward confirming it,
defeating the point of an independent accuracy check. `classifier_accuracy` (eval/metrics.py)
is the only place the two are compared.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from pmigrate.traceback_utils import deepest_first_party_frame
from pmigrate.types import FailureClass

FAILURES_IN = Path("docs/results/triage_failures_dev.jsonl")
LABELLED_OUT = Path("tests/fixtures/triage/labelled_dev.jsonl")

_VALID_CLASSES = sorted(c.value for c in FailureClass)

GroupKey = tuple[str, str | None]


@dataclass(frozen=True)
class LabelledFailure:
    """One row of `labelled_dev.jsonl` -- `eval/metrics.py`'s `classifier_accuracy` is
    the only place `predicted_cls` and `true_cls` are compared; this type is just the
    parsed record."""

    repo_id: str
    node_id: str | None
    predicted_cls: FailureClass
    true_cls: FailureClass
    text: str


def load_labelled(path: Path) -> list[LabelledFailure]:
    return [
        LabelledFailure(
            repo_id=e["repo_id"],
            node_id=e["node_id"],
            predicted_cls=FailureClass(e["predicted_cls"]),
            true_cls=FailureClass(e["true_cls"]),
            text=e["text"],
        )
        for e in _load_jsonl(path)
    ]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _group_key(entry: dict[str, Any]) -> GroupKey:
    return (entry["predicted_cls"], deepest_first_party_frame(entry["text"]))


def main(
    failures_in: Path = FAILURES_IN,
    labelled_out: Path = LABELLED_OUT,
) -> None:
    """`pmigrate triage label` -- resumable interactive hand-labelling session. Quit
    anytime with 'q'; already-labelled groups are skipped on the next run."""
    raw = _load_jsonl(failures_in)
    if not raw:
        typer.echo(f"No failures at {failures_in} -- run a corpus eval with failures_out first.")
        raise typer.Exit(1)

    groups: dict[GroupKey, list[dict[str, Any]]] = defaultdict(list)
    for entry in raw:
        groups[_group_key(entry)].append(entry)

    already_labelled = {_group_key(e) for e in _load_jsonl(labelled_out)}
    pending = [(k, v) for k, v in groups.items() if k not in already_labelled]

    if not pending:
        typer.echo(f"All {len(groups)} groups already labelled in {labelled_out}.")
        raise typer.Exit(0)

    typer.echo(
        f"{len(pending)} of {len(groups)} groups need labelling "
        f"({sum(len(m) for _, m in pending)} raw failures)."
    )
    typer.echo("Valid classes: " + ", ".join(_VALID_CLASSES))
    typer.echo("Type a class name, 's' to see another sample from this group, 'q' to quit.\n")

    labelled_out.parent.mkdir(parents=True, exist_ok=True)
    with labelled_out.open("a") as out:
        for i, (_key, members) in enumerate(pending):
            repos = sorted({m["repo_id"] for m in members})
            typer.echo(
                f"--- group {i + 1}/{len(pending)}: {len(members)} raw failure(s), "
                f"repos: {repos} ---"
            )
            sample_index = 0
            typer.echo(members[sample_index]["text"])

            true_cls: str | None = None
            while true_cls is None:
                answer = typer.prompt("true class").strip().lower()
                if answer == "q":
                    remaining = len(pending) - i
                    typer.echo(f"Stopped. {remaining} group(s) still need labelling.")
                    return
                if answer == "s":
                    sample_index = (sample_index + 1) % len(members)
                    typer.echo(f"\n[sample {sample_index + 1}/{len(members)}]")
                    typer.echo(members[sample_index]["text"])
                    continue
                if answer not in _VALID_CLASSES:
                    typer.echo(f"Not a valid class. Choose from: {', '.join(_VALID_CLASSES)}")
                    continue
                true_cls = answer

            for m in members:
                out.write(
                    json.dumps(
                        {
                            "repo_id": m["repo_id"],
                            "node_id": m["node_id"],
                            "predicted_cls": m["predicted_cls"],
                            "true_cls": true_cls,
                            "text": m["text"],
                        }
                    )
                    + "\n"
                )
            out.flush()
            typer.echo(f"Labelled {len(members)} raw failures as {true_cls!r}.\n")

    typer.echo("All groups labelled.")


if __name__ == "__main__":
    typer.run(main)
