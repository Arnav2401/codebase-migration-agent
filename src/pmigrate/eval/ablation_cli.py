"""`pmigrate eval ablation` — run several arms interleaved by repo (docs/decisions.md D102).

Separate command rather than a flag on `eval run`, because it answers a different question.
`eval run` scores ONE arm and its results stand alone; this compares arms, and a comparison
has a validity requirement `eval run` does not: every arm must have seen comparable
conditions. Running arms as separate commands is exactly what produced a ranking of run
order rather than of retrieval strategy.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from dotenv import load_dotenv

from pmigrate.corpus.manifest_io import load_manifest
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.harness import DEFAULT_CLONE_CACHE_ROOT, run_corpus
from pmigrate.eval.interleave import budget_exhausted_repos, interleaved_plan
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_results_table
from pmigrate.eval.run import _build_model_client
from pmigrate.eval.store import ResultStore, ResumeContext, corpus_sha
from pmigrate.sandbox.runner import DockerSandbox
from pmigrate.trace.writer import DEFAULT_TRACE_ROOT

load_dotenv()
app = typer.Typer()


@app.command()
def main(
    configs: str = typer.Option(..., help="Comma-separated arm names, e.g. 'graph,embedding'"),
    split: str = "dev",
    configs_dir: Path = Path("configs"),
    manifest_path: Path = Path("corpus/manifest.json"),
    work_root: Path = Path("eval_work"),
    results_db: Path = Path("eval_results.db"),
    out_dir: Path = Path("docs/results"),
    clone_cache_root: Path = DEFAULT_CLONE_CACHE_ROOT,
    trace_root: Path = DEFAULT_TRACE_ROOT,
) -> None:
    names = [n.strip() for n in configs.split(",") if n.strip()]
    if len(names) < 2:
        raise typer.BadParameter("an ablation needs at least two arms to compare")

    arms: list[EvalConfig] = []
    for name in names:
        path = configs_dir / f"{name}.json"
        if not path.exists():
            typer.echo(f"no config at {path}", err=True)
            raise typer.Exit(code=1)
        arms.append(EvalConfig.from_dict(json.loads(path.read_text())))

    specs = [r for r in load_manifest(manifest_path) if r.split == split]
    c_sha = corpus_sha(manifest_path)
    plan = interleaved_plan(specs, arms)
    typer.echo(f"interleaved plan: {len(plan)} (repo, arm) cells over {len(specs)} repos")

    store = ResultStore(results_db)
    results_by_arm: dict[str, list[RepoResult]] = {a.name: [] for a in arms}
    scored: set[tuple[str, str]] = set()
    try:
        for i, (repo, config) in enumerate(plan, start=1):
            typer.echo(f"[{i}/{len(plan)}] {repo.repo_id} :: {config.name}")
            out = run_corpus(
                [repo],
                work_root=work_root,
                sandbox=DockerSandbox(),
                model_client=_build_model_client(config),
                config=config,
                split=split,  # type: ignore[arg-type]
                resume=ResumeContext(store=store, corpus_sha=c_sha),
                clone_cache_root=clone_cache_root,
                trace_root=trace_root,
            )
            for result in out:
                results_by_arm[config.name].append(result)
                scored.add((result.repo_id, config.name))
    finally:
        store.close()

    partial = budget_exhausted_repos(plan, scored)
    for name, results in results_by_arm.items():
        # Partially-scored repos are dropped from every arm's table, not just the arm that
        # missed them: keeping them would compare a full arm against a partial one, which
        # is the confound interleaving exists to remove (D102).
        usable = [r for r in results if r.repo_id not in partial]
        write_results_table(usable, out_dir / f"{name}.md", config_name=name)
        typer.echo(f"{name}: {len(usable)} comparable repo(s)")

    if partial:
        typer.echo(
            f"EXCLUDED {len(partial)} repo(s) where not every arm ran "
            f"({', '.join(sorted(partial))}) -- the budget ran out mid-repo, so those "
            "repos cannot support a cross-arm comparison.",
            err=True,
        )
    typer.echo(f"finished at {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    app()
