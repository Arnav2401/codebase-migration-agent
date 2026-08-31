"""Phase 0 steps 3-6 (docs/phase-0-corpus.md) — the Docker-dependent half of validation.

For each RepoSpec in the manifest without a captured baseline:
  3. Build a Docker image at pre_sha with pydantic v1 pinned, install deps.
  4. Run the test suite (timeout-capped).
  5. Run it a SECOND time and require identical pass/fail sets; anything that disagrees
     goes into `flaky` and is excluded from scoring (see docs/phase-0-corpus.md pitfalls).
  6. Gate: >=80% of collected tests pass and >=15 tests pass, else drop and record why.
  7. Sanity-check the other end: build post_sha under pydantic v2 and confirm the human's
     own migration is green. If it isn't, the repo is not usable as ground truth.

NOTE: this is a standalone, Phase-0-scoped Docker runner — deliberately not the general
`Sandbox` protocol from docs/interfaces.md §3, which doesn't exist until Phase 2. When
Phase 2 builds the real sandbox (with network isolation, read-only mounts, resource caps
for AGENT-authored code), this script's build-image logic is the thing to fold into it;
this script only ever runs the repo's OWN test suite, unmodified, so the stakes are lower.

Docker is not installed on this machine as of the last check (docs/phase-0-corpus.md
"Also in this phase") — this script has not been run end-to-end here. Install Docker
Desktop, then run `make corpus-baselines` and expect to debug the first few repos by hand;
the 30-minute-per-repo cap below is a starting point, not a validated number.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import structlog
import typer

from pmigrate.corpus.manifest_io import load_manifest, save_manifest
from pmigrate.types import BaselineResult, RepoSpec

log = structlog.get_logger()
app = typer.Typer()

BUILD_TIMEOUT_S = 30 * 60  # docs/phase-0-corpus.md: cap debugging at 30 min/repo
TEST_TIMEOUT_S = 10 * 60  # docs/phase-0-corpus.md: suite must run in <10 min
MIN_PASS_COUNT = 15
MIN_PASS_FRACTION = 0.80

DOCKERFILE_TEMPLATE = """\
FROM python:{python_version}-slim
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
RUN git clone --quiet {url} . && git checkout --quiet {sha}
{setup_overrides}
RUN pip install --no-cache-dir pytest pytest-json-report "pydantic{pydantic_constraint}"
RUN {install_cmd}
"""


@dataclass
class BaselineOutcome:
    result: BaselineResult | None
    drop_reason: str | None


def _pydantic_constraint(version: Literal["v1", "v2"]) -> str:
    return "<2,>=1.9" if version == "v1" else ">=2,<3"


def _build_image(repo: RepoSpec, pydantic: Literal["v1", "v2"], sha: str) -> str:
    tag = f"pmigrate-corpus:{repo.repo_id}-{sha[:8]}-{pydantic}"
    with tempfile.TemporaryDirectory() as tmp:
        dockerfile = DOCKERFILE_TEMPLATE.format(
            python_version=repo.python_version,
            url=repo.url,
            sha=sha,
            setup_overrides="\n".join(repo.setup_overrides),
            install_cmd=" ".join(repo.install_cmd),
            pydantic_constraint=_pydantic_constraint(pydantic),
        )
        (Path(tmp) / "Dockerfile").write_text(dockerfile)
        subprocess.run(
            ["docker", "build", "-t", tag, tmp],
            check=True,
            capture_output=True,
            timeout=BUILD_TIMEOUT_S,
        )
    return tag


def _run_pytest_json(image: str, test_cmd: tuple[str, ...]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as out_dir:
        report_path = Path(out_dir) / "report.json"
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{out_dir}:/out",
            "--memory",
            "2g",
            "--cpus",
            "2",
            image,
            *test_cmd,
            "--json-report",
            "--json-report-file=/out/report.json",
        ]
        subprocess.run(
            cmd, capture_output=True, timeout=TEST_TIMEOUT_S
        )  # non-zero exit is expected on red suites
        if not report_path.exists():
            raise RuntimeError("pytest did not produce a json report — likely a collection error")
        return cast(dict[str, Any], json.loads(report_path.read_text()))


def _outcomes_from_report(
    report: dict[str, Any],
) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    passed, failed, skipped = set(), set(), set()
    for test in report.get("tests", []):
        node_id, outcome = test["nodeid"], test["outcome"]
        if outcome == "passed":
            passed.add(node_id)
        elif outcome in ("failed", "error"):
            failed.add(node_id)
        elif outcome == "skipped":
            skipped.add(node_id)
    return frozenset(passed), frozenset(failed), frozenset(skipped)


def capture_baseline(repo: RepoSpec) -> BaselineOutcome:
    try:
        image = _build_image(repo, "v1", repo.pre_sha)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return BaselineOutcome(None, f"build failed at pre_sha: {e}")

    try:
        report_1 = _run_pytest_json(image, repo.test_cmd)
        time.sleep(1)
        report_2 = _run_pytest_json(image, repo.test_cmd)
    except (subprocess.TimeoutExpired, RuntimeError) as e:
        return BaselineOutcome(None, f"test run failed: {e}")

    passed_1, failed_1, skipped_1 = _outcomes_from_report(report_1)
    passed_2, failed_2, _ = _outcomes_from_report(report_2)

    flaky = (passed_1 ^ passed_2) | (failed_1 ^ failed_2)
    passed = passed_1 & passed_2  # only tests that agreed both times count (I4 + determinism)

    if len(passed) < MIN_PASS_COUNT:
        return BaselineOutcome(
            None, f"only {len(passed)} tests passed reproducibly, need >= {MIN_PASS_COUNT}"
        )

    total_collected = len(passed_1 | failed_1 | skipped_1)
    if total_collected == 0:
        return BaselineOutcome(None, "zero tests collected")
    pass_fraction = len(passed) / total_collected
    if pass_fraction < MIN_PASS_FRACTION:
        return BaselineOutcome(None, f"pass fraction {pass_fraction:.2f} < {MIN_PASS_FRACTION}")

    result = BaselineResult(
        passed=passed,
        failed=frozenset(failed_1 & failed_2),
        skipped=skipped_1,
        flaky=frozenset(flaky),
        duration_s=report_1.get("duration", 0.0),
    )
    return BaselineOutcome(result, None)


def sanity_check_post_sha(repo: RepoSpec, baseline: BaselineResult) -> tuple[bool, str]:
    """The human's own migration must be green under pydantic v2, or this repo is not
    valid ground truth (docs/phase-0-corpus.md step 6)."""
    try:
        image = _build_image(repo, "v2", repo.post_sha)
        report = _run_pytest_json(image, repo.test_cmd)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as e:
        return False, f"post_sha build/test failed: {e}"

    passed, _, _ = _outcomes_from_report(report)
    still_passing = baseline.passed & passed
    fraction = len(still_passing) / len(baseline.passed) if baseline.passed else 0.0
    if fraction < MIN_PASS_FRACTION:
        return False, f"only {fraction:.2f} of baseline-passing tests still pass at post_sha"
    return True, ""


@app.command()
def main(manifest_path: Path = Path("corpus/manifest.json")) -> None:
    if shutil.which("docker") is None:
        typer.echo(
            "docker not found on PATH. Install Docker Desktop, then re-run this command. "
            "See docs/phase-0-corpus.md 'Also in this phase'.",
            err=True,
        )
        raise typer.Exit(code=1)

    specs = load_manifest(manifest_path)
    updated: list[RepoSpec] = []
    dropped: list[tuple[str, str]] = []

    for spec in specs:
        if spec.baseline is not None:
            updated.append(spec)
            continue

        log.info("capture_baselines.start", repo_id=spec.repo_id)
        outcome = capture_baseline(spec)
        if outcome.result is None:
            dropped.append((spec.repo_id, outcome.drop_reason or "unknown"))
            log.warning(
                "capture_baselines.dropped", repo_id=spec.repo_id, reason=outcome.drop_reason
            )
            continue

        ok, reason = sanity_check_post_sha(spec, outcome.result)
        if not ok:
            dropped.append((spec.repo_id, f"post_sha sanity check failed: {reason}"))
            log.warning("capture_baselines.post_sha_failed", repo_id=spec.repo_id, reason=reason)
            continue

        updated.append(
            RepoSpec(
                repo_id=spec.repo_id,
                url=spec.url,
                pre_sha=spec.pre_sha,
                post_sha=spec.post_sha,
                python_version=spec.python_version,
                install_cmd=spec.install_cmd,
                test_cmd=spec.test_cmd,
                setup_overrides=spec.setup_overrides,
                split=spec.split,
                baseline=outcome.result,
                human_diff_stats=spec.human_diff_stats,
            )
        )
        log.info(
            "capture_baselines.captured", repo_id=spec.repo_id, passed=len(outcome.result.passed)
        )

    save_manifest(updated, manifest_path)

    typer.echo(f"\nBaselines captured: {len(updated)}/{len(specs)}")
    if dropped:
        typer.echo("Dropped:")
        for repo_id, reason in dropped:
            typer.echo(f"  {repo_id}: {reason}")


if __name__ == "__main__":
    app()
