import subprocess
from pathlib import Path

from pmigrate.agent.state import Edit
from pmigrate.eval.harness import compute_diff_similarity
from pmigrate.types import DiffStats, RepoSpec


def _run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _make_human_repo(
    tmp_path: Path, path: str, pre_content: str, post_content: str
) -> tuple[Path, str, str]:
    """A real, throwaway local git repo (no network, no remote) -- `compute_diff_similarity`
    reads `post_sha` content via `git show`, which needs actual git history to run against."""
    repo_dir = tmp_path / "human_repo"
    repo_dir.mkdir()
    _run("git", "init", "-q", cwd=repo_dir)
    _run("git", "config", "user.email", "t@t.com", cwd=repo_dir)
    _run("git", "config", "user.name", "t", cwd=repo_dir)

    file_path = repo_dir / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(pre_content)
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "pre", cwd=repo_dir)
    pre_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)

    file_path.write_text(post_content)
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "post (the human's real fix)", cwd=repo_dir)
    post_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)

    # matches checkout_pre_sha's real behavior: the working tree stays AT pre_sha, even
    # though post_sha is now reachable in local history for _git_show to read.
    _run("git", "checkout", "-q", pre_sha, cwd=repo_dir)

    return repo_dir, pre_sha, post_sha


def _repo(pre_sha: str, post_sha: str, changed_paths: tuple[str, ...] | None) -> RepoSpec:
    diff_stats = (
        DiffStats(
            files_changed=len(changed_paths),
            lines_added=1,
            lines_removed=1,
            changed_paths=changed_paths,
        )
        if changed_paths is not None
        else None
    )
    return RepoSpec(
        repo_id="acme__widgets",
        url="https://example.invalid/acme/widgets",
        pre_sha=pre_sha,
        post_sha=post_sha,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
        human_diff_stats=diff_stats,
    )


def _edit(path: str) -> Edit:
    return Edit(source="T2", unit_module="app.models", files_changed=(path,), diff="")


def test_returns_none_without_human_diff_stats(tmp_path: Path) -> None:
    repo_dir, pre_sha, post_sha = _make_human_repo(tmp_path, "app/models.py", "x = 1\n", "x = 2\n")
    repo = _repo(pre_sha, post_sha, changed_paths=None)
    result = compute_diff_similarity(
        repo, source_root=repo_dir, overlay_root=tmp_path / "overlay", final_state={}
    )
    assert result is None


def test_returns_none_when_no_python_file_is_touched_by_either_side(tmp_path: Path) -> None:
    repo_dir, pre_sha, post_sha = _make_human_repo(tmp_path, "app/models.py", "x = 1\n", "x = 2\n")
    # human_diff_stats lists only a non-.py file; agent's own edits are empty too
    repo = _repo(pre_sha, post_sha, changed_paths=("README.md",))
    result = compute_diff_similarity(
        repo, source_root=repo_dir, overlay_root=tmp_path / "overlay", final_state={}
    )
    assert result is None


def test_full_agreement_when_agent_overlay_matches_the_humans_real_fix(tmp_path: Path) -> None:
    path = "app/models.py"
    repo_dir, pre_sha, post_sha = _make_human_repo(
        tmp_path, path, "x = 1\n", 'x = 2\ny = "fixed"\n'
    )
    overlay_root = tmp_path / "overlay"
    (overlay_root / "app").mkdir(parents=True)
    (overlay_root / path).write_text('x = 2\ny = "fixed"\n')  # identical to the human's real fix

    repo = _repo(pre_sha, post_sha, changed_paths=(path,))
    final_state = {"edits": [_edit(path)]}
    result = compute_diff_similarity(
        repo, source_root=repo_dir, overlay_root=overlay_root, final_state=final_state
    )

    assert result is not None
    assert result.line_jaccard == 1.0
    assert result.symbol_precision == 1.0
    assert result.symbol_recall == 1.0


def test_penalizes_a_file_only_the_human_touched(tmp_path: Path) -> None:
    # the human's real fix touches TWO files; the agent's edits only cover one of them --
    # recall must reflect the miss, since compute_diff_similarity is supposed to catch
    # exactly this asymmetry (docs/decisions.md D58).
    fixed_path = "app/models.py"
    missed_path = "app/settings.py"
    repo_dir = tmp_path / "human_repo"
    repo_dir.mkdir()
    _run("git", "init", "-q", cwd=repo_dir)
    _run("git", "config", "user.email", "t@t.com", cwd=repo_dir)
    _run("git", "config", "user.name", "t", cwd=repo_dir)
    (repo_dir / "app").mkdir()
    (repo_dir / fixed_path).write_text("x = 1\n")
    (repo_dir / missed_path).write_text("y = 1\n")
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "pre", cwd=repo_dir)
    pre_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)

    (repo_dir / fixed_path).write_text("x = 2\n")
    (repo_dir / missed_path).write_text("y = 2\n")  # the human ALSO fixed this file
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "post", cwd=repo_dir)
    post_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)
    _run("git", "checkout", "-q", pre_sha, cwd=repo_dir)  # working tree back to pre_sha

    overlay_root = tmp_path / "overlay"
    (overlay_root / "app").mkdir(parents=True)
    (overlay_root / fixed_path).write_text("x = 2\n")  # agent matches the human here...
    # ...but never touches missed_path at all -- no file written into the overlay for it.

    repo = _repo(pre_sha, post_sha, changed_paths=(fixed_path, missed_path))
    final_state = {"edits": [_edit(fixed_path)]}
    result = compute_diff_similarity(
        repo, source_root=repo_dir, overlay_root=overlay_root, final_state=final_state
    )

    assert result is not None
    assert result.symbol_recall < 1.0  # the missed file must drag recall down
    assert result.symbol_precision == 1.0  # everything the agent DID touch, the human also touched


def test_includes_a_file_only_the_agent_touched(tmp_path: Path) -> None:
    # the agent edits a file the human's real fix never needed -- must drag precision down.
    path = "app/models.py"
    untouched_by_human = "app/extra.py"
    repo_dir = tmp_path / "human_repo"
    repo_dir.mkdir()
    _run("git", "init", "-q", cwd=repo_dir)
    _run("git", "config", "user.email", "t@t.com", cwd=repo_dir)
    _run("git", "config", "user.name", "t", cwd=repo_dir)
    (repo_dir / "app").mkdir()
    (repo_dir / path).write_text("x = 1\n")
    (repo_dir / untouched_by_human).write_text("z = 1\n")
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "pre", cwd=repo_dir)
    pre_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)

    (repo_dir / path).write_text("x = 2\n")
    # untouched_by_human stays the same in the human's real fix
    _run("git", "add", ".", cwd=repo_dir)
    _run("git", "commit", "-q", "-m", "post", cwd=repo_dir)
    post_sha = _run("git", "rev-parse", "HEAD", cwd=repo_dir)
    _run("git", "checkout", "-q", pre_sha, cwd=repo_dir)  # working tree back to pre_sha

    overlay_root = tmp_path / "overlay"
    (overlay_root / "app").mkdir(parents=True)
    (overlay_root / path).write_text("x = 2\n")  # matches human
    (overlay_root / untouched_by_human).write_text("z = 2\n")  # agent ALSO (wrongly) edits this

    repo = _repo(pre_sha, post_sha, changed_paths=(path,))  # human's diff_stats: only `path`
    final_state = {"edits": [_edit(path), _edit(untouched_by_human)]}
    result = compute_diff_similarity(
        repo, source_root=repo_dir, overlay_root=overlay_root, final_state=final_state
    )

    assert result is not None
    assert result.symbol_precision < 1.0  # the extra, unneeded edit must drag precision down
    assert result.symbol_recall == 1.0  # everything the human needed, the agent also did
