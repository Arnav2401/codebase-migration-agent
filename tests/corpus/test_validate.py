"""Unit tests for validate.py's pure mechanical checks. Added after running discovery for
real against live GitHub data (2026-09-01) surfaced two false positives that slipped past
_isolation_ok: commits touching only requirements.txt/lockfiles, with zero source changes,
were accepted as "migrations." _touches_source_file() is the fix; these tests pin down both
the bug and the fix so it can't silently regress.
"""

import subprocess
from pathlib import Path

from pmigrate.corpus.validate import (
    MAX_FILES_TOUCHED,
    MIN_FILES_TOUCHED,
    _find_migration_commit,
    _isolation_ok,
    _pre_sha_is_clean_v1,
    _touches_dependency_file,
    _touches_source_file,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str, **files: str) -> str:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    return repo


def _file(name: str, additions: int = 5, deletions: int = 5) -> dict:
    return {"filename": name, "additions": additions, "deletions": deletions}


def test_touches_dependency_file_true_for_requirements() -> None:
    assert _touches_dependency_file([_file("requirements.txt")])


def test_touches_dependency_file_false_when_absent() -> None:
    assert not _touches_dependency_file([_file("app/models.py")])


def test_touches_source_file_true_for_py_file() -> None:
    assert _touches_source_file([_file("app/models.py")])


def test_touches_source_file_false_for_deps_only() -> None:
    # the real false positive: skygazer42/Weaver touched three dependency files, zero .py
    assert not _touches_source_file(
        [
            _file("requirements.txt"),
            _file("requirements-dev.txt"),
            _file("requirements-optional.txt"),
        ]
    )


def test_touches_source_file_false_for_lockfile_only() -> None:
    # the real false positive: arn-c0de/Crawllama touched pyproject.toml + uv.lock only
    assert not _touches_source_file([_file("pyproject.toml"), _file("uv.lock")])


def test_isolation_rejects_dependency_only_commit() -> None:
    ok, reason = _isolation_ok([_file("requirements.txt"), _file("pyproject.toml")])
    assert ok is False
    assert "source file" in reason


def test_isolation_accepts_real_migration_shape() -> None:
    ok, _ = _isolation_ok(
        [_file("requirements.txt"), _file("app/models.py"), _file("app/settings.py")]
    )
    assert ok is True


def test_isolation_rejects_too_few_files() -> None:
    ok, reason = _isolation_ok([_file("app/models.py")] * (MIN_FILES_TOUCHED - 1))
    assert ok is False
    assert "expected >=" in reason


def test_isolation_rejects_too_many_files() -> None:
    files = [_file(f"app/mod_{i}.py") for i in range(MAX_FILES_TOUCHED + 1)]
    ok, reason = _isolation_ok(files)
    assert ok is False
    assert "bundled" in reason


def test_isolation_rejects_zero_line_changes() -> None:
    files = [_file("app/a.py", 0, 0), _file("requirements.txt", 0, 0)]
    ok, reason = _isolation_ok(files)
    assert ok is False
    assert "no line changes" in reason


def test_isolation_rejects_mostly_net_new_lines() -> None:
    # net-new dominated by additions with almost no deletions looks like a feature add
    files = [_file("app/a.py", 500, 1), _file("requirements.txt", 2, 1)]
    ok, reason = _isolation_ok(files)
    assert ok is False
    assert "net-new-line fraction" in reason


# --- commit-location: real local git repos, no network or mocking needed --------------


def test_find_migration_commit_via_message_and_dependency_diff(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "initial", **{"requirements.txt": "pydantic<2\n", "app.py": "x = 1\n"})
    migration_sha = _commit(
        repo,
        "migrate to pydantic v2",
        **{"requirements.txt": "pydantic>=2\n", "app.py": "x = 2\n"},
    )
    found = _find_migration_commit(repo, "repo")
    assert found == migration_sha


def test_find_migration_commit_falls_back_to_pickaxe_when_message_unhelpful(
    tmp_path: Path,
) -> None:
    # no commit message mentions "pydantic v2" at all — the original single strategy
    # would find nothing here; the pickaxe fallback finds the commit that actually
    # introduced a v2-only symbol, regardless of how the author phrased the message.
    repo = _init_repo(tmp_path)
    _commit(repo, "initial", **{"app.py": "from pydantic import validator\n"})
    migration_sha = _commit(
        repo, "refactor validators", **{"app.py": "from pydantic import field_validator\n"}
    )
    found = _find_migration_commit(repo, "repo")
    assert found == migration_sha


def test_find_migration_commit_returns_none_when_nothing_matches(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "initial", **{"app.py": "x = 1\n"})
    _commit(repo, "unrelated change", **{"app.py": "x = 2\n"})
    assert _find_migration_commit(repo, "repo") is None


# --- pre_sha cleanliness: catches D32's plugboard-shaped bug -----------------------------


def test_pre_sha_is_clean_v1_true_when_no_v2_symbols_anywhere(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    pre_sha = _commit(repo, "initial", **{"app.py": "from pydantic import validator\n"})
    _commit(repo, "migrate", **{"app.py": "from pydantic import field_validator\n"})
    ok, reason = _pre_sha_is_clean_v1(repo, pre_sha, "repo")
    assert ok is True
    assert reason == ""


def test_pre_sha_is_clean_v1_false_when_a_sibling_file_already_uses_v2_syntax(
    tmp_path: Path,
) -> None:
    # the exact real shape found live (docs/decisions.md D32): a workspace sub-package
    # already used pydantic-v2-only syntax at pre_sha, in a file the migration commit
    # never touched at all — a per-commit diff check can't see this; only a repo-wide
    # grep at pre_sha can.
    repo = _init_repo(tmp_path)
    pre_sha = _commit(
        repo,
        "initial",
        **{
            "app.py": "from pydantic import validator\n",
            "schemas/component.py": "from pydantic import field_validator\n",
        },
    )
    _commit(repo, "migrate app.py", **{"app.py": "from pydantic import field_validator\n"})
    ok, reason = _pre_sha_is_clean_v1(repo, pre_sha, "repo")
    assert ok is False
    assert "schemas/component.py" in reason


def test_pre_sha_is_clean_v1_fails_closed_on_a_real_grep_error(
    tmp_path: Path, monkeypatch: object
) -> None:
    # the exact real bug found live: an earlier version of _V2_ONLY_SYMBOLS had
    # unescaped "(" characters, making the -E pattern invalid ERE syntax. `git grep`
    # exited 128 ("empty (sub)expression"), and treating any non-zero returncode as
    # "no match" made every candidate silently report as clean — failing OPEN, the
    # opposite of what this function's whole purpose requires. A returncode >= 2 (a
    # real git-grep error, not "no match" which is 1) must be treated as "could not
    # verify," not "verified clean."
    repo = _init_repo(tmp_path)
    pre_sha = _commit(repo, "initial", **{"app.py": "x = 1\n"})

    class _FakeResult:
        returncode = 128
        stdout = ""
        stderr = "fatal: command line, 'bad(pattern': empty (sub)expression"

    real_run = subprocess.run

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        if "grep" in args:
            return _FakeResult()
        return real_run(args, **kwargs)

    import pmigrate.corpus.validate as validate_mod

    monkeypatch.setattr(validate_mod.subprocess, "run", fake_run)  # type: ignore[attr-defined]
    ok, reason = _pre_sha_is_clean_v1(repo, pre_sha, "repo")
    assert ok is False
    assert "check itself failed" in reason
