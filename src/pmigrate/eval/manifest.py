"""Phase 5's run manifest (docs/decisions.md D63, docs/phase-5-eval.md's "Run manifest
per invocation (I6)" bullet): the record of exactly what a `run_corpus` invocation was --
corpus content, prompt content, model, seed, the agent's own code version, and wall time --
independent of `eval/store.py`'s per-cell result store. A `RepoResult` says what happened
to one repo under one config; a `RunManifest` says what config of the WORLD produced every
result in one invocation, satisfying invariant I6 ("runs reproducible") even for a run that
crashed before any repo finished scoring.

Written twice to the same path, not once: `write_run_manifest` is called with
`ended_at=None` before `run_corpus` starts (so a crashed run still leaves a manifest
describing what was ATTEMPTED) and again with the real `ended_at` once it returns —
matching phase-5-eval.md's "written before the run" while still being able to report
start/end time, which a single pre-run write structurally cannot do honestly.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from pmigrate.eval.config import EvalConfig


@dataclass(frozen=True)
class RunManifest:
    corpus_sha: str
    prompt_hashes: dict[str, str]  # path relative to prompts_dir -> sha256 of its bytes
    model: str
    seed: int
    config: EvalConfig
    agent_git_sha: str
    started_at: float
    temperature: int = 0  # model_client.py's real clients hardcode 0 already (I6) -- not
    # a per-run knob, so recorded as a constant rather than threaded through as a param
    # nothing actually varies.
    ended_at: float | None = None


def build_prompt_hashes(prompts_dir: Path) -> dict[str, str]:
    """sha256 per `*.md` file under `prompts_dir`, keyed by its filename -- CLAUDE.md's
    "prompts are versioned, and are hashed into the run manifest" rule. Sorted so the
    manifest's key order (and therefore its JSON serialization) is deterministic across
    runs on the same prompt set."""
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(prompts_dir.glob("*.md"))
    }


def agent_git_sha(repo_root: Path) -> str:
    """The agent codebase's own HEAD sha at run time -- "which version of the agent
    produced this run," not a corpus repo's sha (that's `RepoSpec.pre_sha`/`post_sha`).
    Real subprocess call, not unit-tested against a fake (same real-I/O carve-out
    `eval/harness.py`'s own module docstring already draws around `checkout_pre_sha`)."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_run_manifest(manifest: RunManifest, out_path: Path) -> None:
    data = asdict(manifest)
    data["config"] = manifest.config.to_dict()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True))
