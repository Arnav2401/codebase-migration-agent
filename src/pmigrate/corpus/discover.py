"""Phase 0 step 1 — cast a wide net for candidate repos.

Produces corpus/candidates.jsonl: one JSON object per candidate repo, each carrying a
best-guess migration commit SHA (from commit-message search) or None (from code search,
where validate.py has to locate the actual migration commit itself by walking history).

Design note (see docs/phase-0-corpus.md step 1): GitHub's search API can search commit
*messages* and current file *contents*, but not historical diff content. So this file
runs two complementary strategies rather than one clever query:

  1. commit-message search — catches repos whose migration commit says what it is
     ("migrate to pydantic v2", "bump pydantic to 2.x", ...). High precision, misses
     migrations with generic commit messages.
  2. code search for v2-only syntax (ConfigDict, field_validator, pydantic_settings
     import) — catches every repo currently on v2 regardless of commit message, at the
     cost of needing validate.py to locate the actual migration commit per candidate.

The query lists and thresholds below are a reasonable starting point, not a settled
answer — expect to widen or narrow them once you see the false-positive/negative rate on
the first run. That tuning is a judgment call worth making yourself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog
import typer

from pmigrate.corpus.github_client import GitHubClient

log = structlog.get_logger()
app = typer.Typer()

CANDIDATES_PATH = Path("corpus/candidates.jsonl")

# Prefilters applied to every hit before it's written out. Cheap checks only — the
# expensive checks (buildable, tests pass) happen in validate.py.
MIN_STARS = 20
MAX_REPO_SIZE_KB = 50_000  # ~50MB; GitHub reports repo `size` in KB

COMMIT_MESSAGE_QUERIES = [
    "pydantic v2 language:python",
    "migrate to pydantic 2 language:python",
    "bump pydantic language:python",
    "pydantic>=2 language:python",
    "pydantic 2.0 migration language:python",
]

CODE_SEARCH_QUERIES = [
    "from pydantic import ConfigDict language:python",
    "from pydantic import field_validator language:python",
    "from pydantic_settings import BaseSettings language:python",
]


@dataclass
class Candidate:
    repo_id: str  # "org__name"
    full_name: str  # "org/name"
    url: str
    stars: int
    size_kb: int
    source: str  # which query surfaced it
    candidate_sha: str | None  # known migration commit, if commit-message search found one
    commit_message: str | None


def _repo_id(full_name: str) -> str:
    return full_name.replace("/", "__")


def _passes_prefilter(repo: dict[str, Any]) -> bool:
    if repo.get("stargazers_count", 0) < MIN_STARS:
        return False
    if repo.get("size", 0) > MAX_REPO_SIZE_KB:
        return False
    if repo.get("archived"):
        return False
    if repo.get("language") not in ("Python", None):
        return False
    # unclear licensing — skip rather than adjudicate
    return bool(repo.get("license"))


def discover(client: GitHubClient, max_pages_per_query: int = 3) -> list[Candidate]:
    seen: dict[str, Candidate] = {}

    for query in COMMIT_MESSAGE_QUERIES:
        for page in range(1, max_pages_per_query + 1):
            result = client.search_commits(query, page=page)
            items = result.get("items", [])
            if not items:
                break
            for item in items:
                repo = item["repository"]
                full_name = repo["full_name"]
                if full_name in seen:
                    continue
                full_repo = client.get_repo(full_name)
                if not _passes_prefilter(full_repo):
                    continue
                seen[full_name] = Candidate(
                    repo_id=_repo_id(full_name),
                    full_name=full_name,
                    url=full_repo["html_url"],
                    stars=full_repo["stargazers_count"],
                    size_kb=full_repo["size"],
                    source=f"commit_message:{query}",
                    candidate_sha=item["sha"],
                    commit_message=item["commit"]["message"].splitlines()[0],
                )
            log.info("discover.commit_search_page", query=query, page=page, hits=len(items))

    for query in CODE_SEARCH_QUERIES:
        for page in range(1, max_pages_per_query + 1):
            result = client.search_code(query, page=page)
            items = result.get("items", [])
            if not items:
                break
            for item in items:
                repo = item["repository"]
                full_name = repo["full_name"]
                if full_name in seen:
                    continue
                full_repo = client.get_repo(full_name)
                if not _passes_prefilter(full_repo):
                    continue
                seen[full_name] = Candidate(
                    repo_id=_repo_id(full_name),
                    full_name=full_name,
                    url=full_repo["html_url"],
                    stars=full_repo["stargazers_count"],
                    size_kb=full_repo["size"],
                    source=f"code_search:{query}",
                    candidate_sha=None,  # validate.py must locate the migration commit
                    commit_message=None,
                )
            log.info("discover.code_search_page", query=query, page=page, hits=len(items))

    return list(seen.values())


@app.command()
def main(max_pages_per_query: int = 3, out: Path = CANDIDATES_PATH) -> None:
    client = GitHubClient()
    candidates = discover(client, max_pages_per_query=max_pages_per_query)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for c in candidates:
            f.write(json.dumps(asdict(c)) + "\n")
    log.info("discover.done", total=len(candidates), out=str(out))


if __name__ == "__main__":
    app()
