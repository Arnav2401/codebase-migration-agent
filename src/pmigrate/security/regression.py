"""Phase 8: a security regression gate over the migration diff.

"Run a scanner before and after the migration; fail the run if the security posture
worsened." The load-bearing word is *worsened*: this compares the two scans and reports
only what the migration INTRODUCED. A repo that already had twenty findings before pmigrate
touched it still has twenty; that is not this tool's doing and failing a run for it would
make the gate unusable on real code.

That is the same principle as invariant I4, which scores only tests that passed at baseline
-- a migration is answerable for what it changed, not for the state it inherited.

Bandit rather than Semgrep: it is a pip-installable Python-native AST scanner, so it adds no
system dependency and runs on the overlay directly. The comparison logic below is
analyzer-agnostic -- `run_scan` is the only Bandit-specific part, and swapping in Semgrep
means replacing that function alone.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

# Bandit's `code` field is the offending line plus context, each line PREFIXED WITH ITS
# LINE NUMBER ("222         assert not self.total"). Keying on it raw makes the key
# line-dependent after all, which is the bug this keying was supposed to avoid: found live
# (docs/decisions.md D99) when the gate reported 9 "introduced" B101 findings on
# `Aiven-Open__rohmu` that were pre-existing asserts, renumbered because T1 had edited the
# file above them. Stripping the prefixes makes the key depend on the CODE only.
_LINE_NUMBER_PREFIX = re.compile(r"^\s*\d+\s?", re.MULTILINE)


def _normalize_code(code: str) -> str:
    """The offending code with bandit's line-number prefixes and indentation removed."""
    without_numbers = _LINE_NUMBER_PREFIX.sub("", code)
    return "\n".join(line.strip() for line in without_numbers.splitlines() if line.strip())


SCAN_TIMEOUT_S = 300


@dataclass(frozen=True)
class Finding:
    """A scanner hit, identified by (test_id, path, code) rather than by line number.

    Line numbers move when a migration edits a file above an untouched finding, which would
    otherwise report the same pre-existing issue as newly introduced -- the exact false
    positive that makes a regression gate get switched off.
    """

    test_id: str
    severity: str
    path: str
    code: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.test_id, self.path, _normalize_code(self.code))


@dataclass(frozen=True)
class RegressionReport:
    introduced: list[Finding]
    resolved: list[Finding]
    pre_count: int
    post_count: int
    scan_failed: str | None = None

    @property
    def worsened(self) -> bool:
        """A scan that could not run is NOT treated as a pass. An unavailable gate that
        reports success is worse than no gate, because it looks like coverage."""
        return bool(self.introduced) or self.scan_failed is not None

    @property
    def worst_introduced(self) -> str | None:
        if not self.introduced:
            return None
        return max(self.introduced, key=lambda f: SEVERITY_ORDER.get(f.severity, 0)).severity

    def render(self) -> str:
        if self.scan_failed:
            return f"SECURITY GATE: could not run ({self.scan_failed}) -- treated as a failure."
        if not self.introduced:
            resolved = (
                f", {len(self.resolved)} pre-existing finding(s) resolved" if self.resolved else ""
            )
            return (
                f"SECURITY GATE: pass -- no new findings "
                f"({self.pre_count} before, {self.post_count} after{resolved})."
            )
        by_sev = Counter(f.severity for f in self.introduced)
        detail = ", ".join(f"{n} {sev.lower()}" for sev, n in sorted(by_sev.items()))
        lines = [
            f"SECURITY GATE: FAIL -- migration introduced "
            f"{len(self.introduced)} finding(s) ({detail}):"
        ]
        lines += [
            f"  [{f.severity}] {f.test_id} {f.path}: {f.code.strip()[:80]}"
            for f in self.introduced[:10]
        ]
        return "\n".join(lines)


def run_scan(root: Path) -> tuple[list[Finding], str | None]:
    """Bandit over `root`. Returns (findings, error). Bandit exits 1 when it FINDS things,
    so the exit code cannot distinguish "issues found" from "scanner broke" -- the presence
    of parseable JSON is what does."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bandit", "-r", str(root), "-f", "json", "-q"],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return [], f"bandit did not run: {exc}"
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], f"bandit produced no parseable JSON (exit {proc.returncode})"
    findings = [
        Finding(
            test_id=r.get("test_id", "?"),
            severity=r.get("issue_severity", "LOW"),
            path=str(Path(r.get("filename", "?")).relative_to(root))
            if str(r.get("filename", "")).startswith(str(root))
            else r.get("filename", "?"),
            code=r.get("code", ""),
        )
        for r in payload.get("results", [])
    ]
    return findings, None


def compare(
    pre: list[Finding], post: list[Finding], *, error: str | None = None
) -> RegressionReport:
    pre_keys = {f.key for f in pre}
    post_keys = {f.key for f in post}
    return RegressionReport(
        introduced=[f for f in post if f.key not in pre_keys],
        resolved=[f for f in pre if f.key not in post_keys],
        pre_count=len(pre),
        post_count=len(post),
        scan_failed=error,
    )


def gate(source_root: Path, overlay_root: Path) -> RegressionReport:
    """Scan before (the untouched checkout) and after (the migrated overlay)."""
    pre, err_pre = run_scan(source_root)
    if err_pre:
        return compare([], [], error=err_pre)
    post, err_post = run_scan(overlay_root)
    if err_post:
        return compare([], [], error=err_post)
    return compare(pre, post)
