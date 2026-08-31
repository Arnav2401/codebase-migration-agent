"""Thin GitHub REST API wrapper for corpus discovery and validation.

Deliberately not using PyGithub here: commit search (`/search/commits`) and the exact
pagination/rate-limit handling we need are simpler to get right against the raw REST API
than through PyGithub's abstraction. PyGithub is still the right tool for Phase 6 (fork +
PR), where its higher-level object model earns its keep.

Requires a GITHUB_TOKEN with at least public read scopes. Without one you get 60 req/hour
and both search endpoints become impractical.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, cast

import requests
import structlog

log = structlog.get_logger()

API_BASE = "https://api.github.com"


class GitHubRateLimited(Exception):
    """Raised when a rate limit is hit and cannot be resolved by waiting the caller's
    configured max wait. Caller decides whether to abort or checkpoint and resume."""


@dataclass
class GitHubClient:
    token: str | None = None
    max_wait_s: int = 120

    def __post_init__(self) -> None:
        self.token = self.token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            log.warning(
                "github_client.no_token",
                msg="No GITHUB_TOKEN set — limited to 60 req/hour, search endpoints "
                "will exhaust this almost immediately. Set GITHUB_TOKEN in .env.",
            )
        self.session = requests.Session()
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)

    def _get(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        for attempt in range(6):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(1, reset - int(time.time()) + 1)
                if wait > self.max_wait_s:
                    raise GitHubRateLimited(f"rate limited, would need to wait {wait}s")
                log.info("github_client.rate_limited", waiting_s=wait, attempt=attempt)
                time.sleep(wait)
                continue
            if resp.status_code == 202:
                # secondary rate limit / not-yet-computed search index; brief backoff
                time.sleep(2**attempt)
                continue
            return resp
        raise GitHubRateLimited("exhausted retries")

    def search_commits(self, query: str, page: int = 1, per_page: int = 100) -> dict[str, Any]:
        """GET /search/commits — full-text search over commit messages, not diff content.
        GitHub does not offer diff-content commit search; discover.py compensates by also
        searching code (search_code) for post-migration API usage as a proxy signal."""
        resp = self._get(
            f"{API_BASE}/search/commits",
            params={"q": query, "page": page, "per_page": per_page, "sort": "committer-date"},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def search_code(self, query: str, page: int = 1, per_page: int = 100) -> dict[str, Any]:
        resp = self._get(
            f"{API_BASE}/search/code",
            params={"q": query, "page": page, "per_page": per_page},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def get_repo(self, full_name: str) -> dict[str, Any]:
        resp = self._get(f"{API_BASE}/repos/{full_name}")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def get_commit(self, full_name: str, sha: str) -> dict[str, Any]:
        """Includes `files` with per-file patch stats and `parents` (parents[0] is pre_sha
        for a normal, non-merge commit)."""
        resp = self._get(f"{API_BASE}/repos/{full_name}/commits/{sha}")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def list_repo_root(self, full_name: str, ref: str) -> list[dict[str, Any]]:
        resp = self._get(f"{API_BASE}/repos/{full_name}/contents", params={"ref": ref})
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())
