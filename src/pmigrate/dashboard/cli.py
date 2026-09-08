"""`pmigrate dashboard` — rebuild the trace index and render the HTML page."""

from __future__ import annotations

from pathlib import Path

import typer

from pmigrate.dashboard.render import write_dashboard
from pmigrate.trace.index import DEFAULT_INDEX_PATH, rebuild
from pmigrate.trace.writer import DEFAULT_TRACE_ROOT

app = typer.Typer()


@app.command()
def main(
    trace_root: Path = DEFAULT_TRACE_ROOT,
    index_path: Path = DEFAULT_INDEX_PATH,
    out: Path = Path("docs/results/dashboard.html"),
) -> None:
    n = rebuild(trace_root=trace_root, index_path=index_path)
    written = write_dashboard(out, index_path=index_path)
    typer.echo(f"indexed {n} run(s) from {trace_root} -> {index_path}")
    typer.echo(f"wrote {written}")


if __name__ == "__main__":
    app()
