"""Invariant I7: PRs only ever go to repositories the operator owns.

phase-6-trace-pr.md is blunt about why -- "Opening unsolicited AI-generated PRs against
real projects is rude, gets you blocked, and would be a genuinely bad look on a portfolio
project." So this is not a warning or a config default: an upstream target raises, and the
allowlist is an explicit list of owners rather than a pattern, because a pattern that
matched `Arnav2401-fork` or `arnav2401` would eventually match something else too.
"""

from __future__ import annotations

import re

# Owners whose repositories this tool may open a PR against. Deliberately hardcoded and
# deliberately tiny (CLAUDE.md I7: "PRs only to Arnav's own forks"). Adding an entry here
# should feel like a decision, not configuration.
ALLOWED_OWNERS: frozenset[str] = frozenset({"Arnav2401"})

_REPO_URL = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?/?$"
)


class ForkTargetError(RuntimeError):
    """Raised when a PR target is not an allowed fork. Its own type, not a ValueError, so a
    caller cannot swallow it with a broad `except ValueError` meant for argument parsing."""


def parse_owner_repo(url_or_slug: str) -> tuple[str, str]:
    """Accepts `owner/repo`, an https URL, or an ssh URL."""
    match = _REPO_URL.match(url_or_slug.strip())
    if match:
        return match.group("owner"), match.group("repo")
    parts = url_or_slug.strip().strip("/").split("/")
    if len(parts) == 2 and all(parts):
        return parts[0], parts[1]
    raise ForkTargetError(f"cannot parse a GitHub owner/repo out of {url_or_slug!r}")


def is_allowed_target(url_or_slug: str) -> bool:
    try:
        owner, _ = parse_owner_repo(url_or_slug)
    except ForkTargetError:
        return False
    return owner in ALLOWED_OWNERS


def assert_allowed_target(url_or_slug: str) -> tuple[str, str]:
    """The chokepoint. Every code path that could open a PR must go through this."""
    owner, repo = parse_owner_repo(url_or_slug)
    if owner not in ALLOWED_OWNERS:
        raise ForkTargetError(
            f"REFUSING to target {owner}/{repo}: invariant I7 permits PRs only to "
            f"{sorted(ALLOWED_OWNERS)}. Fork the repo first and target the fork. "
            "Opening unsolicited AI-generated PRs against upstream projects is exactly "
            "what this invariant exists to prevent."
        )
    return owner, repo
