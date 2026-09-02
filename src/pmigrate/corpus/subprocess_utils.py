"""Shared subprocess-error formatting for the corpus scripts (validate.py,
capture_baselines.py). Kept separate so neither imports the other, matching
manifest_io.py's own rationale.
"""

from __future__ import annotations

import subprocess


def subprocess_error_detail(e: subprocess.CalledProcessError | subprocess.TimeoutExpired) -> str:
    """`str(CalledProcessError)` is just "Command '[...]' returned non-zero exit status
    N." — the actual reason (the command's own stderr) is a separate attribute nothing
    was reading. Found live in validate.py (docs/decisions.md D33): a `-S "ConfigDict("`
    pickaxe search failed against a partial clone with a real, specific git error
    ("attempting to fetch ... which is in the commit graph file but not in the object
    database" — a promisor-remote fetch failure, not a bug in the search itself), and
    every log line for it said only "exit status 128," indistinguishable from any other
    failure without re-running the command by hand to find out what actually happened.
    Extracted to a shared module (D39) once capture_baselines.py hit the identical gap
    for `docker build` failures — same fix, same reasoning, don't duplicate it a second
    time in a second file."""
    stderr = e.stderr
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    return f"{e}: {stderr.strip()}" if stderr else str(e)
