"""Phase 0 step 2 — mechanical validation funnel (docs/phase-0-corpus.md step 2).

Consumes corpus/candidates.jsonl (from discover.py), applies the git/API-level checks that
don't need Docker, and writes surviving candidates as draft RepoSpec entries into
corpus/manifest.json. Every drop is recorded with a reason in corpus/logs/drop_reasons.jsonl
so the funnel produces the histogram docs/phase-0-corpus.md asks for.

What this script does NOT do (see capture_baselines.py instead): build a Docker image,
install dependencies, or run the test suite. Those need Docker, which is not yet installed
on this machine — see docs/phase-0-corpus.md "Also in this phase". Splitting the pipeline
this way means the git/API-only checks below are runnable today.

Checks implemented here (docs/phase-0-corpus.md step 2, items 1-2):
  1. The migration commit is a real migration, not a version-pin bump.
  2. The migration is reasonably isolated — not bundled with an unrelated feature.

Checks NOT yet implemented here (require Docker — see capture_baselines.py):
  3. Buildable at pre_sha.
  4. Test suite runs in <10 min under pydantic v1.
  5. Baseline is meaningfully green (>=80% of collected tests, >=15 tests).
  6. Human's post_sha is green under pydantic v2.

Thresholds (MIN_FILES_TOUCHED, MAX_FILES_TOUCHED, MAX_NET_NEW_LINE_FRACTION) are starting
points from the brief, not settled — tune them against the false-positive/negative rate
you actually see, and note in docs/decisions.md if you change them meaningfully.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import typer

from pmigrate.corpus.github_client import GitHubClient
from pmigrate.corpus.manifest_io import load_manifest, save_manifest
from pmigrate.corpus.subprocess_utils import subprocess_error_detail
from pmigrate.types import DiffStats, RepoSpec

log = structlog.get_logger()
app = typer.Typer()

CANDIDATES_PATH = Path("corpus/candidates.jsonl")
CHECKOUTS_DIR = Path("corpus/checkouts")
DROP_LOG_PATH = Path("corpus/logs/drop_reasons.jsonl")

DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
}

MIN_FILES_TOUCHED = 2  # a real migration touches at least a model file + a dep file
MAX_FILES_TOUCHED = 40  # beyond this, likely bundled with an unrelated feature
MAX_NET_NEW_LINE_FRACTION = 0.30  # net-new lines / total changed lines


@dataclass
class DropReason:
    repo_id: str
    stage: str
    reason: str


def _log_drop(reasons: list[DropReason], repo_id: str, stage: str, reason: str) -> None:
    reasons.append(DropReason(repo_id=repo_id, stage=stage, reason=reason))
    log.info("validate.drop", repo_id=repo_id, stage=stage, reason=reason)


def _touches_dependency_file(files: list[dict[str, Any]]) -> bool:
    return any(Path(f["filename"]).name in DEPENDENCY_FILES for f in files)


def _touches_source_file(files: list[dict[str, Any]]) -> bool:
    """A commit that only bumps requirements.txt/pyproject.toml with no .py change isn't
    a migration — it's a version-pin edit with nothing for the agent to learn from. Found
    by hand-checking two of the four early "survivors" (skygazer42/Weaver,
    arn-c0de/Crawllama): both touched only dependency/lockfiles, zero source changes."""
    return any(
        f["filename"].endswith(".py") and f["filename"] not in DEPENDENCY_FILES for f in files
    )


def _isolation_ok(files: list[dict[str, Any]]) -> tuple[bool, str]:
    n = len(files)
    if n < MIN_FILES_TOUCHED:
        return False, f"only {n} files touched, expected >= {MIN_FILES_TOUCHED}"
    if n > MAX_FILES_TOUCHED:
        return False, f"{n} files touched, likely bundled with an unrelated feature"
    if not _touches_source_file(files):
        return False, "no .py source file touched — likely just a dependency-pin bump"
    additions = sum(f.get("additions", 0) for f in files)
    deletions = sum(f.get("deletions", 0) for f in files)
    total = additions + deletions
    if total == 0:
        return False, "no line changes reported"
    net_new_fraction = max(0, additions - deletions) / total
    if net_new_fraction > MAX_NET_NEW_LINE_FRACTION:
        return (
            False,
            f"net-new-line fraction {net_new_fraction:.2f} suggests a feature add, not a migration",
        )
    return True, ""


def _clone_shallow(client: GitHubClient, full_name: str, repo_id: str) -> Path | None:
    """Cloned once per candidate now, not just for code-search-sourced ones with no known
    commit — `_pre_sha_is_clean_v1` below needs a real checkout for every candidate
    regardless of how its migration commit was found (docs/decisions.md D32: the gap that
    let `plugboard` through wasn't in commit-location at all)."""
    checkout = CHECKOUTS_DIR / repo_id
    if checkout.exists():
        shutil.rmtree(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                client.get_repo(full_name)["clone_url"],
                str(checkout),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("validate.clone_failed", repo_id=repo_id, error=subprocess_error_detail(e))
        return None
    return checkout


# Tried in order of specificity, not combined with AND — docs/decisions.md D33: the
# original single query (commit message mentions "pydantic v2" AND the diff touches a
# dependency file with a pydantic-related change) dropped 36 of 46 real candidates at
# this stage. Real migrations don't reliably phrase their commit message a specific way,
# and a repo may have bumped its dependency file in an earlier, separate commit from the
# one that actually rewrote the source. The pickaxe strategies (`-S`) are the most
# robust: they find the commit that changed whether a v2-only symbol's occurrence count
# in the tree, which doesn't depend on commit message wording at all.
_COMMIT_SEARCH_STRATEGIES: tuple[tuple[str, ...], ...] = (
    (
        "--all",
        "--format=%H",
        "-i",
        "--grep=pydantic.*v\\?2",
        "-G",
        "pydantic",
        "--",
        *DEPENDENCY_FILES,
    ),
    ("--all", "--format=%H", "-i", "--grep=pydantic.*v\\?2"),
    ("--all", "--format=%H", "-S", "field_validator", "--", "*.py"),
    ("--all", "--format=%H", "-S", "ConfigDict(", "--", "*.py"),
    ("--all", "--format=%H", "-S", "model_dump(", "--", "*.py"),
)


def _find_migration_commit(checkout: Path, repo_id: str) -> str | None:
    """For candidates with no known commit: search git log with several distinct
    strategies, in order, stopping at the first one that finds anything. Heuristic, not
    exhaustive — expect to hand-fix a few of these during curation."""
    for args in _COMMIT_SEARCH_STRATEGIES:
        try:
            log_out = subprocess.run(
                ["git", "-C", str(checkout), "log", *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            ).stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            log.warning(
                "validate.log_search_failed", repo_id=repo_id, error=subprocess_error_detail(e)
            )
            continue
        if log_out:
            # Most recent matching commit is usually the actual migration (later commits
            # tend to be follow-up fixes) — take the first line, but this is exactly the
            # kind of hit that deserves a human glance during curation rather than blind
            # trust. (--format=%H, not --oneline: --oneline abbreviates to a 7-char hash,
            # which silently produced a truncated post_sha in the manifest until that was
            # caught by inspection.)
            return log_out.splitlines()[0]
    return None


# A repo-wide grep at pre_sha, not a diff check — docs/decisions.md D32: `plugboard`'s
# migration commit was real and correctly isolated, but its `pre_sha` was NOT a genuine
# pre-migration state — a workspace sub-package (`plugboard-schemas`) had already
# independently moved to pydantic v2 syntax before the commit Phase 0 identified as "the"
# migration. A per-commit diff check can never catch this, because the offending code was
# never touched by that commit at all; it requires looking at the whole tree.
_V2_ONLY_SYMBOLS = (
    "field_validator",
    "model_validator",
    r"ConfigDict\(",
    r"model_dump\(",
    "model_config =",
    "model_config:",
)


def _pre_sha_is_clean_v1(checkout: Path, pre_sha: str, repo_id: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--quiet", pre_sha],
            check=True,
            capture_output=True,
            timeout=60,
        )
        result = subprocess.run(
            [
                "git",
                "-C",
                str(checkout),
                "grep",
                "-l",
                "-E",
                "|".join(_V2_ONLY_SYMBOLS),
                "--",
                "*.py",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        detail = subprocess_error_detail(e)
        log.warning("validate.pre_sha_check_failed", repo_id=repo_id, error=detail)
        return False, f"could not verify pre_sha is clean: {detail}"  # fail closed, not open

    # `git grep` uses its exit code for three DIFFERENT meanings: 0 = matched, 1 = no
    # match (a normal, expected outcome — NOT an error), >=2 = a real error (bad pattern,
    # bad pathspec, ...). Found live: an earlier version of `_V2_ONLY_SYMBOLS` had
    # unescaped `(` characters, which made the `-E` pattern invalid ERE syntax — git
    # exited 128 with "empty (sub)expression," and treating "returncode != 0" as "no
    # match" made this fail OPEN (silently reporting every candidate as clean) instead of
    # failing closed the way this function's own docstring/comment already claimed to.
    if result.returncode not in (0, 1):
        log.warning("validate.pre_sha_check_failed", repo_id=repo_id, error=result.stderr.strip())
        return False, f"pre_sha check itself failed: {result.stderr.strip()}"
    if result.returncode == 0 and result.stdout.strip():
        hit = result.stdout.strip().splitlines()[0]
        return False, f"pre_sha already contains pydantic v2-only syntax (e.g. {hit})"
    return True, ""


def validate_candidate(
    client: GitHubClient, candidate: dict[str, Any], reasons: list[DropReason]
) -> RepoSpec | None:
    repo_id = candidate["repo_id"]
    full_name = candidate["full_name"]

    checkout = _clone_shallow(client, full_name, repo_id)
    if checkout is None:
        _log_drop(reasons, repo_id, "locate_commit", "could not clone repo")
        return None

    sha = candidate.get("candidate_sha")
    if sha is None:
        sha = _find_migration_commit(checkout, repo_id)
        if sha is None:
            _log_drop(reasons, repo_id, "locate_commit", "could not locate a migration commit")
            return None

    commit = client.get_commit(full_name, sha)
    if len(commit.get("parents", [])) != 1:
        _log_drop(reasons, repo_id, "locate_commit", "migration commit is a merge or has no parent")
        return None
    pre_sha = commit["parents"][0]["sha"]
    files = commit.get("files", [])

    if not _touches_dependency_file(files):
        _log_drop(reasons, repo_id, "isolation", "migration commit doesn't touch a dependency file")
        return None

    ok, reason = _isolation_ok(files)
    if not ok:
        _log_drop(reasons, repo_id, "isolation", reason)
        return None

    clean, reason = _pre_sha_is_clean_v1(checkout, pre_sha, repo_id)
    if not clean:
        _log_drop(reasons, repo_id, "pre_sha_not_clean", reason)
        return None

    repo_meta = client.get_repo(full_name)
    diff_stats = DiffStats(
        files_changed=len(files),
        lines_added=sum(f.get("additions", 0) for f in files),
        lines_removed=sum(f.get("deletions", 0) for f in files),
        changed_paths=tuple(f["filename"] for f in files),
    )

    return RepoSpec(
        repo_id=repo_id,
        url=repo_meta["html_url"],
        pre_sha=pre_sha,
        post_sha=sha,
        python_version="3.11",  # TODO(human): confirm per-repo; check setup.py/CI config
        install_cmd=("pip", "install", "-e", ".[test]"),  # TODO(human): verify per repo
        test_cmd=("pytest", "-q"),
        split="dev",  # curation step reassigns this; see docs/phase-0-corpus.md step 3
        human_diff_stats=diff_stats,
    )


@app.command()
def main(
    candidates_path: Path = CANDIDATES_PATH,
    manifest_path: Path = Path("corpus/manifest.json"),
) -> None:
    if not candidates_path.exists():
        raise typer.BadParameter(f"{candidates_path} not found — run discover.py first")

    client = GitHubClient()
    reasons: list[DropReason] = []
    survivors: list[RepoSpec] = []

    with candidates_path.open() as f:
        candidates = [json.loads(line) for line in f if line.strip()]

    for candidate in candidates:
        spec = validate_candidate(client, candidate, reasons)
        if spec is not None:
            survivors.append(spec)

    existing = {s.repo_id for s in load_manifest(manifest_path)}
    new = [s for s in survivors if s.repo_id not in existing]
    save_manifest(load_manifest(manifest_path) + new, manifest_path)

    DROP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DROP_LOG_PATH.open("w") as f:
        for r in reasons:
            f.write(json.dumps({"repo_id": r.repo_id, "stage": r.stage, "reason": r.reason}) + "\n")

    by_stage: dict[str, int] = {}
    for r in reasons:
        by_stage[r.stage] = by_stage.get(r.stage, 0) + 1

    log.info(
        "validate.done",
        candidates=len(candidates),
        survived=len(survivors),
        newly_added=len(new),
        drop_by_stage=by_stage,
    )
    typer.echo(f"\n{len(survivors)}/{len(candidates)} candidates survived mechanical validation.")
    typer.echo(f"Drop reasons by stage: {by_stage}")
    typer.echo(f"Full drop log: {DROP_LOG_PATH}")
    typer.echo(
        "\nNext: run `make corpus-baselines` to build, install, and run these repos under "
        "Docker (requires Docker installed — see docs/phase-0-corpus.md), then hand-curate "
        "the survivors per step 3 before freezing the manifest."
    )


if __name__ == "__main__":
    app()
