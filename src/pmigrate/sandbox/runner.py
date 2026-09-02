"""DockerSandbox: implements the Sandbox protocol (protocol.py) for real, via subprocess
+ the Docker CLI. Verified against a live Docker daemon on 2026-09-01 — see
docs/phase-2-sandbox.md's acceptance criteria for what was checked (determinism, network
isolation, hostile-fixture containment, cache-hit timing) and docs/decisions.md D13 for a
real bug that verification found: the timeout handler looked correct and passed every
mocked unit test, but didn't actually stop the container on a live daemon until fixed.

`--continue-on-collection-errors` is passed unconditionally — verified locally (no Docker
needed for this part) that without it, a single broken import in one file aborts pytest's
ENTIRE session and `report["tests"]` comes back empty even for unrelated, perfectly good
test files. That is the single most common failure mode this whole project exists to
handle correctly; getting this flag wrong would make every migration look like it deleted
the test suite.

Every container gets an explicit, unique `--name` (see policy.py) so the TimeoutExpired
handler below can force-kill it by name — `--rm` alone only removes a container once
something has actually stopped it, and killing the `docker run` CLI process does not do
that (docs/decisions.md D13).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from pmigrate.sandbox.image import build_image
from pmigrate.sandbox.policy import OUTPUT_MOUNT_PATH, build_run_args
from pmigrate.sandbox.results import parse_json_report
from pmigrate.types import ImageRef, RepoSpec, SandboxPolicy, TestRun

REPORT_FILENAME = "report.json"
KILL_TIMEOUT_S = 15  # bounded wait for the force-kill itself; never block indefinitely


def _timeout_result(timeout_s: int, extra_note: str = "") -> TestRun:
    message = f"sandbox run timed out after {timeout_s}s"
    if extra_note:
        message = f"{message} ({extra_note})"
    return TestRun(
        outcomes=(),
        collection_errors=(message,),
        exit_code=-1,
        duration_s=float(timeout_s),
        truncated=False,
    )


def _crashed_result(detail: str) -> TestRun:
    return TestRun(
        outcomes=(),
        collection_errors=(detail,),
        exit_code=-1,
        duration_s=0.0,
        truncated=False,
    )


def _decode(output: bytes | str | None) -> str:
    if output is None:
        return ""
    return output.decode(errors="replace") if isinstance(output, bytes) else output


# docs/decisions.md D43: pytest's own behavior, not a bug here — `--continue-on-collection-
# errors` only smooths over per-FILE collection errors during normal collection; a FATAL
# conftest.py load failure (a single first-party import chain error at the very top,
# reached by nearly every real test module) aborts the whole session before that flag ever
# gets a chance to apply, and before the json-report plugin's finish hook can write
# anything. Found live: a real corpus repo (Aiven-Open/rohmu) hit exactly this shape
# (`@root_validator` raising `PydanticUserError` at class-definition time, imported by
# conftest.py) and the ONLY diagnostic previously available was the generic placeholder
# below — the real, perfectly legible pytest error was sitting in `result.stderr` the
# whole time, captured by `subprocess.run` but never read.
_CRASH_TAIL_CHARS = 4000


class DockerSandbox:
    """Implements the Sandbox protocol (protocol.py) against a real Docker daemon."""

    def build(self, repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> ImageRef:
        return build_image(repo, pydantic)

    def run_tests(
        self,
        image: ImageRef,
        workdir_overlay: Path | None,
        policy: SandboxPolicy,
        selection: list[str] | None = None,
    ) -> TestRun:
        with tempfile.TemporaryDirectory() as out_dir:
            out_path = Path(out_dir)
            report_path_in_container = f"{OUTPUT_MOUNT_PATH}/{REPORT_FILENAME}"
            command = [
                *image.test_cmd,
                *(selection or []),
                "--continue-on-collection-errors",
                "-p",
                "no:randomly",
                "--json-report",
                f"--json-report-file={report_path_in_container}",
            ]
            container_name = f"pmigrate-run-{uuid.uuid4().hex[:12]}"
            args = build_run_args(
                policy,
                image_tag=image.tag,
                output_dir=out_path,
                overlay_dir=workdir_overlay,
                command=command,
                container_name=container_name,
            )

            try:
                result = subprocess.run(args, capture_output=True, timeout=policy.timeout_s)
            except subprocess.TimeoutExpired:
                # Verified against a live daemon (docs/decisions.md D13): killing the
                # `docker run` CLI process here does NOT stop the container — the daemon
                # keeps it running orphaned. --rm only removes a container on its OWN
                # exit, so an explicit `docker kill` by name is what actually triggers
                # that exit (and therefore the removal). Best-effort: if even the kill
                # times out, there's nothing more this call can do — the container is
                # named and logged in the returned error for manual cleanup.
                try:
                    subprocess.run(
                        ["docker", "kill", container_name],
                        capture_output=True,
                        timeout=KILL_TIMEOUT_S,
                    )
                except subprocess.TimeoutExpired:
                    note = f"AND force-kill of container {container_name} also timed out"
                    return _timeout_result(policy.timeout_s, extra_note=f"{note} — check manually")
                return _timeout_result(
                    policy.timeout_s, extra_note=f"container {container_name} force-killed"
                )

            report_file = out_path / REPORT_FILENAME
            if not report_file.exists():
                # docs/decisions.md D43: the real reason is almost always sitting in
                # stderr/stdout already (a fatal conftest.py import error is the common
                # case, not an actual crash) — surface it instead of a placeholder.
                stderr = _decode(result.stderr)[-_CRASH_TAIL_CHARS:]
                stdout = _decode(result.stdout)[-_CRASH_TAIL_CHARS:]
                detail = stderr.strip() or stdout.strip()
                message = (
                    f"no json report produced (exit code {result.returncode}) — "
                    "container likely crashed, was OOM killed, or a fatal error (often a "
                    "conftest.py import failure) aborted the whole pytest session before "
                    "the json-report plugin could write output"
                )
                if detail:
                    message = f"{message}:\n{detail}"
                return _crashed_result(message)

            try:
                report = json.loads(report_file.read_text())
            except json.JSONDecodeError:
                return _crashed_result("json report was truncated or malformed")

            return parse_json_report(report)
