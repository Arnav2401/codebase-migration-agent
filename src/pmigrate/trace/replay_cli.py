"""`pmigrate replay <run_id>` — phase-6-trace-pr.md's completeness test for the trace.

Reconstructs a run from its events alone. Deliberately reads nothing else: not
`eval_results.db`, not the overlay, not the corpus manifest. If the printed timeline cannot
explain what the run did, the trace is incomplete and that is the finding, rather than
something to paper over by joining against the data the trace was supposed to capture.
"""

from __future__ import annotations

from pathlib import Path

import typer

from pmigrate.trace.reader import load_events, replay_timeline
from pmigrate.trace.writer import DEFAULT_TRACE_ROOT

app = typer.Typer()


@app.command()
def main(
    run_id: str = typer.Argument(..., help="Run to replay -- the stem of traces/<run_id>.jsonl"),
    trace_root: Path = DEFAULT_TRACE_ROOT,
) -> None:
    try:
        events = load_events(run_id, trace_root=trace_root)
    except FileNotFoundError as exc:
        available = (
            sorted(p.stem for p in trace_root.glob("*.jsonl")) if trace_root.exists() else []
        )
        typer.echo(f"{exc}\navailable runs: {available}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(replay_timeline(events).render())


if __name__ == "__main__":
    app()
