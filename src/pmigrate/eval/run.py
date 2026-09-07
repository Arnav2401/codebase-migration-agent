"""`pmigrate eval run` (docs/decisions.md D64, phase-5-eval.md's "make eval CONFIG=...
SPLIT=..." deliverable) — the CLI entrypoint tying together every Phase 5 piece built so
far: `EvalConfig` (D57/D60/D61/D62), `run_corpus` (D40/D57), the resumable `ResultStore`
and `RunManifest` (D63), and `eval/report.py`'s per-arm table (this step).

Configs are plain JSON, not YAML — `pyproject.toml` has no YAML dependency, and JSON lets
`configs/*.json` round-trip through `EvalConfig.to_dict`/`from_dict` (D63) directly rather
than adding a parser this project has no other use for.

Real `ModelClient` construction is an explicit whitelist keyed by `config.model`
(`_MODEL_CLIENT_FACTORIES` below), not a guessed prefix rule ("starts with 'gemini'") —
this project has exactly two verified real clients; guessing at a naming convention for
providers that don't exist here yet would be speculative, not implemented. Extending the
`model_*` ablation arm to a third provider is exactly "add one more entry here."

`--max-workers`/`--total-usd-cap` (docs/decisions.md D66) pass straight through to
`run_corpus`'s own params of the same name — see that function's docstring for what each
actually does (and doesn't: `total_usd_cap` stops STARTING new repos, not in-flight ones).

`--clone-cache-root` (docs/decisions.md D70) also passes straight through to
`run_corpus`/`checkout_pre_sha` — defaults to the same `clone_cache/` path
`harness.py`'s `DEFAULT_CLONE_CACHE_ROOT` uses, kept independent of `--work-root` on
purpose so a caller pointing `work_root` at a fresh/scratch location per run doesn't
also silently throw away the one thing that's expensive to rebuild.

`--seeds` (docs/decisions.md D72, phase-5-eval.md's k=3 seed-variance protocol) is a
comma-separated list of ints, default `"0"` -- preserves this command's exact original
single-run behavior when unset. Each named seed runs the SAME `EvalConfig` (via
`dataclasses.replace`, only `seed` differs) through its own `run_corpus` call: `seed` is
already part of `EvalConfig.to_dict`/`config_hash` (D63), so seed=0/1/2 are already
independently resumable DB cells with their own `usd_cap_per_repo` budget -- nothing
about the store or budget semantics changes, this just drives multiple such calls from
one invocation instead of requiring three hand-edited config files. One `RunManifest` is
written per seed (`{config}.manifest.json` for the single-seed default, matching every
existing manifest exactly; `{config}.seed{n}.manifest.json` per seed once more than one
is named) but all seeds' `RepoResult`s are combined into ONE `{config}.md` via
`write_results_table`, which groups by `repo_id` across seeds (D72).

Not unit-tested against real Docker/network (matches `eval/harness.py`'s own
`run_corpus` carve-out — `checkout_pre_sha` itself IS unit-tested, against a real local
git repo, see that module's docstring) — `main`'s own orchestration is exercised by a
live `make eval` run, not pytest. `_build_model_client` and the JSON config loading ARE
pure enough to unit test directly.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import typer
from dotenv import load_dotenv

from pmigrate.agent.model_client import GeminiModelClient, GroqModelClient, ModelClient
from pmigrate.corpus.manifest_io import load_manifest
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.harness import DEFAULT_CLONE_CACHE_ROOT, run_corpus
from pmigrate.eval.manifest import (
    RunManifest,
    agent_git_sha,
    build_prompt_hashes,
    write_run_manifest,
)
from pmigrate.eval.metrics import RepoResult
from pmigrate.eval.report import write_results_table
from pmigrate.eval.store import ResultStore, ResumeContext, corpus_sha
from pmigrate.sandbox.runner import DockerSandbox

load_dotenv()  # matches corpus/github_client.py's own convention -- real API keys
# (GEMINI_API_KEY, GROQ_API_KEY) live in .env, not the shell environment.

app = typer.Typer()

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "agent" / "prompts"

_MODEL_CLIENT_FACTORIES: dict[str, Callable[[str], ModelClient]] = {
    "gemini-3.6-flash": lambda model: GeminiModelClient.from_env(model=model),
    "openai/gpt-oss-120b": lambda model: GroqModelClient.from_env(model=model),
}


def _build_model_client(config: EvalConfig) -> ModelClient | None:
    """None for a t1_only config (docs/decisions.md D62) -- run_corpus/run_repo already
    treat model_client=None as "no repair," and D62's own consistency check would reject
    a t1_only config paired with a real client anyway, so returning None here is the only
    value that could ever be correct for that arm."""
    if "T2" not in config.tiers:
        return None
    factory = _MODEL_CLIENT_FACTORIES.get(config.model)
    if factory is None:
        raise ValueError(
            f"no ModelClient wired up for model={config.model!r} -- known models: "
            f"{sorted(_MODEL_CLIENT_FACTORIES)}"
        )
    return factory(config.model)


@app.command()
def main(
    # typer.Option(...) (a required option), not a plain default -- a bare `config: str`
    # would be inferred as a POSITIONAL argument, breaking the `--config $(CONFIG)` flag
    # form phase-5-eval.md's own "make eval CONFIG=... SPLIT=..." deliverable line uses.
    config: str = typer.Option(..., help="Arm name -- looks up configs/<name>.json"),
    split: str = "dev",
    configs_dir: Path = Path("configs"),
    manifest_path: Path = Path("corpus/manifest.json"),
    work_root: Path = Path("eval_work"),
    results_db: Path = Path("eval_results.db"),
    out_dir: Path = Path("docs/results"),
    max_workers: int = 1,
    total_usd_cap: float | None = None,
    clone_cache_root: Path = DEFAULT_CLONE_CACHE_ROOT,
    seeds: str = typer.Option(
        "0",
        help=(
            "Comma-separated seeds to run this config under (docs/decisions.md D72, "
            "phase-5-eval.md's k=3 seed-variance protocol), e.g. '0,1,2'. Each seed is "
            "an independently resumable run of the same config; results from every "
            "seed are combined into one docs/results/<config>.md."
        ),
    ),
) -> None:
    if split not in ("dev", "test"):
        raise typer.BadParameter(f"split must be 'dev' or 'test', got {split!r}")
    if max_workers < 1:
        raise typer.BadParameter(f"max_workers must be >= 1, got {max_workers}")

    try:
        seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip()]
    except ValueError as exc:
        raise typer.BadParameter(
            f"seeds must be a comma-separated list of ints, got {seeds!r}"
        ) from exc
    if not seed_list:
        raise typer.BadParameter("seeds must name at least one seed")
    if len(set(seed_list)) != len(seed_list):
        raise typer.BadParameter(f"seeds must not repeat, got {seeds!r}")

    config_path = configs_dir / f"{config}.json"
    if not config_path.exists():
        available = sorted(p.stem for p in configs_dir.glob("*.json"))
        typer.echo(f"no config at {config_path} -- available: {available}", err=True)
        raise typer.Exit(code=1)
    base_config = EvalConfig.from_dict(json.loads(config_path.read_text()))

    if shutil.which("docker") is None:
        typer.echo(
            "docker not found on PATH. Install Docker Desktop, then re-run this command. "
            "See docs/phase-0-corpus.md 'Also in this phase'.",
            err=True,
        )
        raise typer.Exit(code=1)

    specs = load_manifest(manifest_path)
    c_sha = corpus_sha(manifest_path)

    all_results: list[RepoResult] = []
    store = ResultStore(results_db)
    try:
        for seed in seed_list:
            eval_config = replace(base_config, seed=seed)
            model_client = _build_model_client(eval_config)

            manifest = RunManifest(
                corpus_sha=c_sha,
                prompt_hashes=build_prompt_hashes(_PROMPTS_DIR),
                model=eval_config.model,
                seed=eval_config.seed,
                config=eval_config,
                agent_git_sha=agent_git_sha(Path.cwd()),
                started_at=time.time(),
            )
            manifest_name = (
                f"{config}.manifest.json"
                if len(seed_list) == 1
                else f"{config}.seed{seed}.manifest.json"
            )
            manifest_out = out_dir / manifest_name
            write_run_manifest(manifest, manifest_out)

            results = run_corpus(
                specs,
                work_root=work_root,
                sandbox=DockerSandbox(),
                model_client=model_client,
                config=eval_config,
                split=split,  # type: ignore[arg-type]
                resume=ResumeContext(store=store, corpus_sha=c_sha),
                max_workers=max_workers,
                total_usd_cap=total_usd_cap,
                clone_cache_root=clone_cache_root,
            )

            write_run_manifest(replace(manifest, ended_at=time.time()), manifest_out)
            all_results.extend(results)
    finally:
        store.close()

    write_results_table(all_results, out_dir / f"{config}.md", config_name=base_config.name)

    full_green = sum(1 for r in all_results if r.full_green)
    typer.echo(
        f"{len(all_results)} repo x seed runs scored across {len(seed_list)} seed(s) "
        f"— {full_green} individually full green"
    )


if __name__ == "__main__":
    app()
