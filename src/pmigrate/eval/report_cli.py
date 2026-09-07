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

Scoped the same way to each arm's CURRENT `configs/<arm>.json` (docs/decisions.md D77).
`corpus_sha` alone was not enough: an arm re-pointed at a different model or given a new
`max_prompt_tokens` keeps its NAME, so grouping by name alone silently averaged rows from
two different configurations under one heading. Found live — after the six ablation arms
moved to NVIDIA (D76), the store held 21 Gemini rows and 7 NVIDIA rows for `graph`, and
this command would have reported their mean as a single "graph" number across two
different MODELS, which is a strictly worse version of the confound D74 already documents.
Rows from superseded configurations stay in the store as history (D74 cites them); they
are simply not mixed into a report describing the current one.

`seed` is deliberately EXCLUDED from that identity comparison. It is part of `config_hash`
(D63, so each seed resumes independently) but running the same arm under seeds 0/1/2 is one
configuration measured k times, not three configurations -- the whole point of D72's k=3
protocol. Matching on the full hash silently dropped seeds 1 and 2 from every report, which
made a k=3 run indistinguishable from a k=1 run: caught immediately after D77 landed,
when a 21-row `t1_only` sweep still reported 7 rows.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import typer

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_main_report
from pmigrate.eval.store import ResultStore, config_hash, corpus_sha

app = typer.Typer()


def _identity(config: EvalConfig) -> str:
    """`config_hash` with `seed` normalized away (D77). Seeds are repeated measurements of
    ONE configuration, not different configurations, so they must not partition a report."""
    return config_hash(replace(config, seed=0))


@app.command()
def main(
    results_db: Path = Path("eval_results.db"),
    manifest_path: Path = Path("corpus/manifest.json"),
    out_path: Path = Path("docs/results/main.md"),
    configs_dir: Path = Path("configs"),
) -> None:
    c_sha = corpus_sha(manifest_path)
    store = ResultStore(results_db)
    try:
        results = store.load_all(corpus_sha=c_sha)
    finally:
        store.close()

    # D77: one configuration identity per arm name -- whatever configs/<arm>.json says
    # TODAY, compared with `seed` normalized away so a k=3 sweep (D72) counts as one
    # configuration measured three times rather than three superseded ones.
    current_identity_by_arm = {}
    for config_path in sorted(configs_dir.glob("*.json")):
        config = EvalConfig.from_dict(json.loads(config_path.read_text()))
        current_identity_by_arm[config.name] = _identity(config)

    results_by_config: dict[str, list[RepoResult]] = {}
    skipped = 0
    for result in results:
        name = result.config.name
        # An arm with no config file at all (deleted since it was run) is dropped rather
        # than reported unqualified: there is no current configuration to say it describes.
        if current_identity_by_arm.get(name) != _identity(result.config):
            skipped += 1
            continue
        results_by_config.setdefault(name, []).append(result)

    write_main_report(results_by_config, out_path)
    scoped = sum(len(v) for v in results_by_config.values())
    typer.echo(f"{scoped} results across {len(results_by_config)} arm(s) — wrote {out_path}")
    if skipped:
        typer.echo(
            f"skipped {skipped} result(s) from superseded configurations "
            "(different model/tiers/budget than the current configs/*.json) — D77"
        )


if __name__ == "__main__":
    app()
