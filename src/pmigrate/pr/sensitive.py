"""Phase 7a's hard rule: a diff touching auth, crypto, secrets or CI blocks PR creation
until a human approves it.

phase-7-guardrails.md is specific that this must be "a path/content matcher in `pr/`, not
a prompt instruction", and the reason is the same one 7b gives for capability containment:
an instruction the model is asked to follow is a request, while a check the PR path must
cross is a guarantee. A model that has been talked into editing `.github/workflows` by a
comment in a repo cannot talk this out of firing.

Matching is deliberately broad. A false positive costs one human glance; a false negative
means an automated PR silently altering CI or credential handling in a repo, which is the
single worst outcome this project could produce.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Path patterns. `.github/workflows` is called out by the spec; CI config more broadly is
# included because a migration PR has no business touching any of it, whatever it is called.
_SENSITIVE_PATHS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ci", re.compile(r"(^|/)\.github/workflows/", re.I)),
    ("ci", re.compile(r"(^|/)(\.gitlab-ci\.yml|azure-pipelines\.yml|Jenkinsfile)$", re.I)),
    ("ci", re.compile(r"(^|/)\.circleci/", re.I)),
    ("secrets", re.compile(r"(^|/)(\.env|\.env\..+|secrets?\.(ya?ml|json|toml|py))$", re.I)),
    ("secrets", re.compile(r"(^|/)(credentials?|\.netrc|\.npmrc|\.pypirc)$", re.I)),
    ("secrets", re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$", re.I)),
    ("auth", re.compile(r"(^|/)(auth|authn|authz|login|session|permissions?|acl)[^/]*\.py$", re.I)),
    (
        "crypto",
        re.compile(r"(^|/)(crypto|cipher|encrypt|decrypt|signing|signature)[^/]*\.py$", re.I),
    ),
    ("packaging", re.compile(r"(^|/)(setup\.py|pyproject\.toml|setup\.cfg)$", re.I)),
)

# Content patterns, applied to ADDED diff lines only. A migration that starts handling
# tokens or shelling out is doing something a pydantic v1->v2 change never needs to.
_SENSITIVE_CONTENT: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "secrets",
        re.compile(r"\b(api[_-]?key|secret|password|passwd|token|private[_-]?key)\b", re.I),
    ),
    ("crypto", re.compile(r"\b(hashlib|hmac|cryptography|Crypto|jwt|bcrypt|passlib)\b")),
    ("exec", re.compile(r"\b(subprocess|os\.system|eval|exec|__import__|pickle\.loads)\b")),
    ("network", re.compile(r"\b(requests\.|urllib|httpx|socket\.|urlopen)\b")),
)


@dataclass(frozen=True)
class SensitiveHit:
    category: str
    where: str
    detail: str


def scan_paths(paths: list[str]) -> list[SensitiveHit]:
    hits: list[SensitiveHit] = []
    for path in paths:
        for category, pattern in _SENSITIVE_PATHS:
            if pattern.search(path):
                hits.append(SensitiveHit(category, path, f"path matches {pattern.pattern}"))
    return hits


def scan_diff(diff: str) -> list[SensitiveHit]:
    """Only ADDED lines. A migration that REMOVES a line mentioning a token is not
    introducing a credential path, and flagging removals would make any diff that touches a
    file near auth code unreviewable for the wrong reason."""
    hits: list[SensitiveHit] = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for category, pattern in _SENSITIVE_CONTENT:
            match = pattern.search(line)
            if match:
                hits.append(
                    SensitiveHit(category, "diff", f"added line matches {match.group(0)!r}")
                )
    return hits


def requires_human_approval(paths: list[str], diff: str = "") -> list[SensitiveHit]:
    """Every hit, de-duplicated. A non-empty result MUST block PR creation (Phase 7a)."""
    seen: dict[tuple[str, str, str], SensitiveHit] = {}
    for hit in [*scan_paths(paths), *scan_diff(diff)]:
        seen.setdefault((hit.category, hit.where, hit.detail), hit)
    return list(seen.values())
