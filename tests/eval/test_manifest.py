import json
import subprocess
from pathlib import Path

from pmigrate.eval.config import EvalConfig
from pmigrate.eval.manifest import (
    RunManifest,
    agent_git_sha,
    build_prompt_hashes,
    write_run_manifest,
)


def _run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _run("git", "init", "-q", cwd=repo_dir)
    _run("git", "config", "user.email", "t@t.com", cwd=repo_dir)
    _run("git", "config", "user.name", "t", cwd=repo_dir)
    (repo_dir / "f.txt").write_text("x")
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "init", cwd=repo_dir)
    sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)
    return repo_dir, sha


def test_agent_git_sha_matches_a_real_repos_head(tmp_path: Path) -> None:
    repo_dir, expected_sha = _init_repo(tmp_path)
    assert agent_git_sha(repo_dir) == expected_sha


def test_build_prompt_hashes_keys_by_filename_and_hashes_content(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "repair_system.md").write_text("You are a migration agent.")
    (prompts_dir / "other.md").write_text("Something else.")
    (prompts_dir / "not_a_prompt.txt").write_text("ignored")

    hashes = build_prompt_hashes(prompts_dir)

    assert set(hashes) == {"repair_system.md", "other.md"}
    assert len(hashes["repair_system.md"]) == 64  # sha256 hex digest length


def test_build_prompt_hashes_changes_when_content_changes(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "repair_system.md"
    prompt_file.write_text("version one")
    hash_before = build_prompt_hashes(prompts_dir)["repair_system.md"]

    prompt_file.write_text("version two")
    hash_after = build_prompt_hashes(prompts_dir)["repair_system.md"]

    assert hash_before != hash_after


def test_write_run_manifest_produces_valid_json_with_a_serialized_config(tmp_path: Path) -> None:
    manifest = RunManifest(
        corpus_sha="deadbeef",
        prompt_hashes={"repair_system.md": "abc123"},
        model="gemini-3.6-flash",
        seed=0,
        config=EvalConfig(name="graph", model="gemini-3.6-flash"),
        agent_git_sha="cafef00d",
        started_at=100.0,
    )
    out_path = tmp_path / "manifest.json"

    write_run_manifest(manifest, out_path)

    data = json.loads(out_path.read_text())
    assert data["corpus_sha"] == "deadbeef"
    assert data["ended_at"] is None
    assert data["temperature"] == 0
    assert data["config"] == {
        "name": "graph",
        "model": "gemini-3.6-flash",
        "retrieval": "graph",
        "tiers": ["T1", "T2", "T3"],
        "triage": True,
        "seed": 0,
        "usd_cap_per_repo": 5.0,
    }


def test_write_run_manifest_called_twice_ends_with_the_final_ended_at(tmp_path: Path) -> None:
    out_path = tmp_path / "manifest.json"
    config = EvalConfig(name="graph", model="gemini-3.6-flash")
    started = RunManifest(
        corpus_sha="deadbeef",
        prompt_hashes={},
        model="gemini-3.6-flash",
        seed=0,
        config=config,
        agent_git_sha="cafef00d",
        started_at=100.0,
    )
    write_run_manifest(started, out_path)

    finished = RunManifest(
        corpus_sha=started.corpus_sha,
        prompt_hashes=started.prompt_hashes,
        model=started.model,
        seed=started.seed,
        config=started.config,
        agent_git_sha=started.agent_git_sha,
        started_at=started.started_at,
        ended_at=150.0,
    )
    write_run_manifest(finished, out_path)

    data = json.loads(out_path.read_text())
    assert data["ended_at"] == 150.0
    assert data["started_at"] == 100.0
