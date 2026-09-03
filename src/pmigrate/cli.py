"""pmigrate CLI entrypoint. Phase 0 only wires up the corpus subcommands; later phases
add `pmigrate eval`, `pmigrate agent run`, `pmigrate replay`, etc. as they're built."""

from __future__ import annotations

import typer

from pmigrate.corpus import capture_baselines, discover, validate
from pmigrate.eval import run as eval_run
from pmigrate.triage import label

app = typer.Typer(help="Autonomous Pydantic v1->v2 migration agent.")

corpus_app = typer.Typer(help="Build and validate the migration corpus (Phase 0).")
corpus_app.command("discover")(discover.main)
corpus_app.command("validate")(validate.main)
corpus_app.command("capture-baselines")(capture_baselines.main)
app.add_typer(corpus_app, name="corpus")

triage_app = typer.Typer(help="Failure triage: classification, grouping (Phase 4).")
triage_app.command("label")(label.main)
app.add_typer(triage_app, name="triage")

eval_app = typer.Typer(help="Run the migration loop across the corpus and score it (Phase 5).")
eval_app.command("run")(eval_run.main)
app.add_typer(eval_app, name="eval")


if __name__ == "__main__":
    app()
