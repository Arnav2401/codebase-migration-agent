"""Shared traceback-parsing helpers. Extracted out of `agent/repair.py` while building
Phase 4 triage (docs/decisions.md D31/D36): `triage/grouping.py` needs the exact same
"which first-party file is really responsible for this failure" answer
`agent/repair.py`'s target-file identification already computes. D31 found the concrete
cost of NOT sharing logic like this — two Dockerfile-building modules drifted out of sync
for months before anyone noticed. Doing the extraction now, the first time a second real
caller exists, avoids repeating that mistake here.
"""

from __future__ import annotations

import re

from pmigrate.agent.patch import is_test_path

_FIRST_PARTY_TRACEBACK_PATH = re.compile(r"^([\w][\w/.\-]*\.py):(\d+):", re.MULTILINE)


def first_party_frames(text: str, *, exclude_test_paths: bool = True) -> list[str]:
    """Every first-party path (`some/module.py`, not an absolute stdlib/site-packages
    path) mentioned as a traceback frame in `text`, in the order printed — outermost
    call frame first, deepest last. A path is "first-party" here simply because pytest
    prints first-party frames relative to the repo root and everything else (stdlib,
    site-packages) as an absolute path; found true against every real corpus traceback
    this project has hit so far, not assumed."""
    paths = [p for p, _lineno in _FIRST_PARTY_TRACEBACK_PATH.findall(text)]
    if exclude_test_paths:
        paths = [p for p in paths if not is_test_path(p)]
    return paths


def deepest_first_party_frame(text: str, *, exclude_test_paths: bool = True) -> str | None:
    """The LAST first-party frame before the trace drops into a third-party file — the
    deepest point of first-party responsibility. Found live (docs/decisions.md D19): for
    a crash INSIDE first-party code (an import error, a bad type annotation evaluated at
    class-body time), this is reliably the file that actually needs fixing — the
    opposite end of the list (`first_party_frames(...)[0]`) is usually just the entry
    point (a test, or `__init__.py`) that happened to trigger it."""
    frames = first_party_frames(text, exclude_test_paths=exclude_test_paths)
    return frames[-1] if frames else None
