"""pmigrate CLI entrypoint. Phase 0 only wires up the corpus subcommands; later phases
add `pmigrate eval`, `pmigrate agent run`, `pmigrate replay`, etc. as they're built."""

from __future__ import annotations

import typer

from pmigrate.corpus import capture_baselines, discover, validate

app = typer.Typer(help="Autonomous Pydantic v1->v2 migration agent.")

corpus_app = typer.Typer(help="Build and validate the migration corpus (Phase 0).")
corpus_app.command("discover")(discover.main)
corpus_app.command("validate")(validate.main)
corpus_app.command("capture-baselines")(capture_baselines.main)
app.add_typer(corpus_app, name="corpus")


if __name__ == "__main__":
    app()
