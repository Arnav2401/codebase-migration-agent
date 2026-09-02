from pathlib import Path

import pmigrate.corpus.capture_baselines as cb
from pmigrate.corpus.manifest_io import load_manifest, save_manifest
from pmigrate.types import BaselineResult, RepoSpec


def _spec(repo_id: str, **overrides: object) -> RepoSpec:
    base = dict(
        repo_id=repo_id,
        url=f"https://github.com/acme/{repo_id}",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
    )
    base.update(overrides)
    return RepoSpec(**base)  # type: ignore[arg-type]


def test_render_dockerfile_uses_system_pip_for_plain_pip_repos() -> None:
    repo = _spec("plain", install_cmd=("pip", "install", "-e", ".[test]"))
    dockerfile = cb._render_dockerfile(repo, "v2", repo.pre_sha)
    assert "pip install --no-cache-dir pytest pytest-json-report" in dockerfile
    assert 'pip install --no-cache-dir --upgrade --force-reinstall "pydantic>=2,<3"' in dockerfile
    assert "pydantic-settings" in dockerfile


def test_render_dockerfile_uses_uv_for_uv_repos() -> None:
    # docs/decisions.md D31: this script's own Dockerfile template had silently regressed
    # to missing both the uv-aware install path (D27) and the pydantic-settings extra
    # package (D20) — neither fix, made in sandbox/image.py, had ever been ported here.
    # Reusing sandbox.image's helpers directly means a future fix there can't drift out
    # of sync with this script again the same way.
    repo = _spec("uv-repo", install_cmd=("uv", "sync", "--group", "test"))
    dockerfile = cb._render_dockerfile(repo, "v2", repo.pre_sha)
    # /repo, not /repo-base — this script's own WORKDIR (docs/decisions.md D31)
    assert "uv pip install --python /repo/.venv/bin/python" in dockerfile
    assert "pytest pytest-json-report" in dockerfile
    assert '--force-reinstall "pydantic>=2,<3"' in dockerfile
    assert "pydantic-settings" in dockerfile
    assert "pip install --no-cache-dir pytest pytest-json-report" not in dockerfile


def test_render_dockerfile_omits_pydantic_settings_for_v1() -> None:
    repo = _spec("plain")
    dockerfile = cb._render_dockerfile(repo, "v1", repo.pre_sha)
    assert "pydantic-settings" not in dockerfile
    assert '"pydantic<2,>=1.9"' in dockerfile


def _baseline(passed: int = 20) -> BaselineResult:
    return BaselineResult(
        passed=frozenset(f"t{i}" for i in range(passed)),
        failed=frozenset(),
        skipped=frozenset(),
        flaky=frozenset(),
        duration_s=1.0,
    )


def test_a_repo_with_existing_baseline_is_preserved_untouched(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "manifest.json"
    spec = _spec("has-baseline", baseline=_baseline())
    save_manifest([spec], manifest_path)
    monkeypatch.setattr(cb.shutil, "which", lambda _: "/usr/bin/docker")
    calls = []
    monkeypatch.setattr(cb, "capture_baseline", lambda s: calls.append(s) or None)

    cb.main(manifest_path=manifest_path)

    assert calls == []  # never re-captured — already had a baseline
    result = load_manifest(manifest_path)
    assert len(result) == 1
    assert result[0].baseline is not None


def test_a_repo_that_fails_baseline_capture_is_kept_not_dropped(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    # the exact real bug found live: main() used to build `updated` by only appending
    # specs that succeeded, then save_manifest(updated, ...) overwrote the whole
    # hand-curated file — a repo that failed baseline capture THIS run vanished from the
    # manifest entirely rather than staying present with baseline=None.
    manifest_path = tmp_path / "manifest.json"
    spec = _spec("fails-baseline")
    save_manifest([spec], manifest_path)
    monkeypatch.setattr(cb.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        cb, "capture_baseline", lambda s: cb.BaselineOutcome(None, "pass fraction 0.5 < 0.8")
    )

    cb.main(manifest_path=manifest_path)

    result = load_manifest(manifest_path)
    assert len(result) == 1  # still present
    assert result[0].repo_id == "fails-baseline"
    assert result[0].baseline is None


def test_a_repo_that_fails_post_sha_sanity_check_is_kept_not_dropped(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec = _spec("fails-sanity")
    save_manifest([spec], manifest_path)
    monkeypatch.setattr(cb.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(cb, "capture_baseline", lambda s: cb.BaselineOutcome(_baseline(), None))
    monkeypatch.setattr(cb, "sanity_check_post_sha", lambda s, b: (False, "post_sha broke"))

    cb.main(manifest_path=manifest_path)

    result = load_manifest(manifest_path)
    assert len(result) == 1
    assert result[0].repo_id == "fails-sanity"
    assert result[0].baseline is None  # never got a baseline written


def test_a_repo_that_succeeds_gets_its_baseline_populated(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    spec = _spec("succeeds")
    save_manifest([spec], manifest_path)
    baseline = _baseline()
    monkeypatch.setattr(cb.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(cb, "capture_baseline", lambda s: cb.BaselineOutcome(baseline, None))
    monkeypatch.setattr(cb, "sanity_check_post_sha", lambda s, b: (True, ""))

    cb.main(manifest_path=manifest_path)

    result = load_manifest(manifest_path)
    assert len(result) == 1
    assert result[0].baseline is not None
    assert result[0].baseline.passed == baseline.passed


def test_mixed_batch_keeps_every_repo_present_regardless_of_outcome(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    manifest_path = tmp_path / "manifest.json"
    specs = [_spec("ok"), _spec("bad")]
    save_manifest(specs, manifest_path)
    baseline = _baseline()
    monkeypatch.setattr(cb.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_capture(s: RepoSpec) -> cb.BaselineOutcome:
        if s.repo_id == "ok":
            return cb.BaselineOutcome(baseline, None)
        return cb.BaselineOutcome(None, "build failed")

    monkeypatch.setattr(cb, "capture_baseline", fake_capture)
    monkeypatch.setattr(cb, "sanity_check_post_sha", lambda s, b: (True, ""))

    cb.main(manifest_path=manifest_path)

    result = {r.repo_id: r for r in load_manifest(manifest_path)}
    assert set(result) == {"ok", "bad"}  # neither vanished
    assert result["ok"].baseline is not None
    assert result["bad"].baseline is None
