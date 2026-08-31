"""Read/write corpus/manifest.json as a list of RepoSpec.

Kept deliberately separate from discover.py/validate.py so both can share one
serialization format without importing each other. This is the only place that knows
how a RepoSpec round-trips to JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pmigrate.types import BaselineResult, DiffStats, RepoSpec

DEFAULT_MANIFEST_PATH = Path("corpus/manifest.json")


def _baseline_to_dict(b: BaselineResult | None) -> dict[str, Any] | None:
    if b is None:
        return None
    return {
        "passed": sorted(b.passed),
        "failed": sorted(b.failed),
        "skipped": sorted(b.skipped),
        "flaky": sorted(b.flaky),
        "duration_s": b.duration_s,
    }


def _baseline_from_dict(d: dict[str, Any] | None) -> BaselineResult | None:
    if d is None:
        return None
    return BaselineResult(
        passed=frozenset(d["passed"]),
        failed=frozenset(d["failed"]),
        skipped=frozenset(d["skipped"]),
        flaky=frozenset(d.get("flaky", [])),
        duration_s=d["duration_s"],
    )


def _diff_stats_to_dict(d: DiffStats | None) -> dict[str, Any] | None:
    return asdict(d) if d is not None else None


def _diff_stats_from_dict(d: dict[str, Any] | None) -> DiffStats | None:
    if d is None:
        return None
    return DiffStats(
        files_changed=d["files_changed"],
        lines_added=d["lines_added"],
        lines_removed=d["lines_removed"],
        changed_paths=tuple(d["changed_paths"]),
    )


def repo_spec_to_dict(spec: RepoSpec) -> dict[str, Any]:
    return {
        "repo_id": spec.repo_id,
        "url": spec.url,
        "pre_sha": spec.pre_sha,
        "post_sha": spec.post_sha,
        "python_version": spec.python_version,
        "install_cmd": list(spec.install_cmd),
        "test_cmd": list(spec.test_cmd),
        "setup_overrides": list(spec.setup_overrides),
        "split": spec.split,
        "baseline": _baseline_to_dict(spec.baseline),
        "human_diff_stats": _diff_stats_to_dict(spec.human_diff_stats),
    }


def repo_spec_from_dict(d: dict[str, Any]) -> RepoSpec:
    return RepoSpec(
        repo_id=d["repo_id"],
        url=d["url"],
        pre_sha=d["pre_sha"],
        post_sha=d["post_sha"],
        python_version=d["python_version"],
        install_cmd=tuple(d["install_cmd"]),
        test_cmd=tuple(d["test_cmd"]),
        setup_overrides=tuple(d.get("setup_overrides", [])),
        split=d.get("split", "dev"),
        baseline=_baseline_from_dict(d.get("baseline")),
        human_diff_stats=_diff_stats_from_dict(d.get("human_diff_stats")),
    )


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> list[RepoSpec]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [repo_spec_from_dict(d) for d in data]


def save_manifest(specs: list[RepoSpec], path: Path = DEFAULT_MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [repo_spec_to_dict(s) for s in specs]
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
