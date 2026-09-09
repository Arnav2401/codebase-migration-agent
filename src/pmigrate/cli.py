"""pmigrate CLI entrypoint. Phase 0 only wires up the corpus subcommands; later phases
add `pmigrate eval`, `pmigrate agent run`, `pmigrate replay`, etc. as they're built."""

from __future__ import annotations

import typer

from pmigrate.corpus import capture_baselines, discover, validate
from pmigrate.dashboard import cli as dashboard_cli
from pmigrate.eval import ablation_cli
from pmigrate.eval import report_cli as eval_report
from pmigrate.eval import run as eval_run
from pmigrate.trace import replay_cli
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
eval_app.command("ablation")(ablation_cli.main)
eval_app.command("report")(eval_report.main)
app.add_typer(eval_app, name="eval")

# Phase 6a: replay is the trace's completeness test, so it is a top-level verb --
# `pmigrate replay <run_id>` exactly as phase-6-trace-pr.md names it.
app.command("replay")(replay_cli.main)
app.command("dashboard")(dashboard_cli.main)


if __name__ == "__main__":
    app()
