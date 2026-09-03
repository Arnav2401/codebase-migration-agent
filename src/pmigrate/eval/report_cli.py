"""`pmigrate eval report` (docs/decisions.md D65) — combines every arm's results already
sitting in the SQLite store (written by `pmigrate eval run`, `eval/run.py`) into
`docs/results/main.md`'s cross-arm headline table with bootstrap 95% CIs, closing the gap
docs/interfaces.md §8's D64 implementation note named ("docs/results/main.md's cross-arm
combination with bootstrap 95% CIs"). A separate command/file from `eval/run.py`, matching
this codebase's one-file-per-command convention (`corpus/discover.py`, `corpus/validate.py`,
`corpus/capture_baselines.py`) — `run` executes ONE arm; `report` only reads what's
already stored, no Docker/model-client/network involved at all.

Scoped to the CURRENT `corpus/manifest.json`'s content hash by default, not every row the
store has ever seen — a report silently mixing results scored against a since-changed
corpus (a repo added/dropped/re-baselined) would combine runs that aren't actually
comparable, the same reasoning `eval/store.py`'s own `corpus_sha` keying already applies
to resumability.
"""

from __future__ import annotations

from pathlib import Path

import typer

from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_main_report
from pmigrate.eval.store import ResultStore, corpus_sha

app = typer.Typer()


@app.command()
def main(
    results_db: Path = Path("eval_results.db"),
    manifest_path: Path = Path("corpus/manifest.json"),
    out_path: Path = Path("docs/results/main.md"),
) -> None:
    c_sha = corpus_sha(manifest_path)
    store = ResultStore(results_db)
    try:
        results = store.load_all(corpus_sha=c_sha)
    finally:
        store.close()

    results_by_config: dict[str, list[RepoResult]] = {}
    for result in results:
        results_by_config.setdefault(result.config.name, []).append(result)

    write_main_report(results_by_config, out_path)
    typer.echo(f"{len(results)} results across {len(results_by_config)} arm(s) — wrote {out_path}")


if __name__ == "__main__":
    app()
