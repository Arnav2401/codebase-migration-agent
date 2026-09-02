import subprocess

import pmigrate.sandbox.image as image_mod
from pmigrate.sandbox.image import build_image, compute_deps_hash, image_tag, render_dockerfile
from pmigrate.types import RepoSpec


def _spec(**overrides: object) -> RepoSpec:
    base = dict(
        repo_id="acme__widgets",
        url="https://github.com/acme/widgets",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "-e", ".[test]"),
        test_cmd=("pytest", "-q"),
    )
    base.update(overrides)
    return RepoSpec(**base)  # type: ignore[arg-type]


def test_deps_hash_deterministic() -> None:
    spec = _spec()
    assert compute_deps_hash(spec) == compute_deps_hash(spec)


def test_deps_hash_changes_with_install_cmd() -> None:
    a = compute_deps_hash(_spec())
    b = compute_deps_hash(_spec(install_cmd=("pip", "install", ".")))
    assert a != b


def test_deps_hash_changes_with_setup_overrides() -> None:
    a = compute_deps_hash(_spec())
    b = compute_deps_hash(_spec(setup_overrides=("RUN apt-get install -y libpq-dev",)))
    assert a != b


def test_deps_hash_insensitive_to_url_and_test_cmd() -> None:
    # the cache key is about what gets INSTALLED, not how tests are invoked or where the
    # repo lives — two manifest entries that differ only in url/test_cmd should share a
    # build if everything else matches.
    a = compute_deps_hash(_spec())
    b = compute_deps_hash(_spec(url="https://github.com/fork/widgets", test_cmd=("pytest", "-x")))
    assert a == b


def test_image_tag_includes_repo_sha_prefix_and_pydantic_version() -> None:
    spec = _spec()
    tag_v1 = image_tag(spec, "v1")
    tag_v2 = image_tag(spec, "v2")
    assert spec.repo_id in tag_v1
    assert spec.pre_sha[:8] in tag_v1
    assert tag_v1 != tag_v2  # different pydantic version must not collide


def test_render_dockerfile_pins_pydantic_v1_range() -> None:
    dockerfile = render_dockerfile(_spec(), "v1")
    assert '"pydantic<2,>=1.9"' in dockerfile
    assert "git checkout --quiet " + "a" * 40 in dockerfile


def test_render_dockerfile_pins_pydantic_v2_range() -> None:
    dockerfile = render_dockerfile(_spec(), "v2")
    assert '"pydantic>=2,<3"' in dockerfile


def test_render_dockerfile_includes_setup_overrides() -> None:
    dockerfile = render_dockerfile(
        _spec(setup_overrides=("RUN apt-get install -y libpq-dev",)), "v2"
    )
    assert "RUN apt-get install -y libpq-dev" in dockerfile


def test_render_dockerfile_uses_repo_base_and_entrypoint() -> None:
    dockerfile = render_dockerfile(_spec(), "v2")
    assert "WORKDIR /repo-base" in dockerfile
    assert 'ENTRYPOINT ["/entrypoint.sh"]' in dockerfile


def test_build_image_short_circuits_on_cache_hit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = []
    monkeypatch.setattr(image_mod, "_image_exists", lambda tag: True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append((a, k)) or None)
    ref = build_image(_spec(), "v2")
    assert calls == []  # docker build was never invoked
    assert ref.pydantic == "v2"
    assert ref.test_cmd == ("pytest", "-q")


def test_render_dockerfile_installs_pydantic_settings_for_v2() -> None:
    dockerfile = render_dockerfile(_spec(), "v2")
    assert "pydantic-settings" in dockerfile


def test_render_dockerfile_omits_pydantic_settings_for_v1() -> None:
    dockerfile = render_dockerfile(_spec(), "v1")
    assert "pydantic-settings" not in dockerfile


def test_render_dockerfile_pins_pydantic_via_system_pip_for_plain_pip_repos() -> None:
    dockerfile = render_dockerfile(_spec(), "v2")
    assert 'pip install --no-cache-dir --upgrade --force-reinstall "pydantic>=2,<3"' in dockerfile


def test_render_dockerfile_pins_pydantic_via_uv_for_uv_repos() -> None:
    # docs/decisions.md D27: `uv sync` installs into an isolated `.venv` it manages
    # itself — a plain system `pip install --force-reinstall` would silently pin the
    # wrong Python's pydantic, one `uv run pytest` never actually uses.
    dockerfile = render_dockerfile(_spec(install_cmd=("uv", "sync", "--group", "test")), "v2")
    assert "uv pip install --python /repo-base/.venv/bin/python" in dockerfile
    assert '--force-reinstall "pydantic>=2,<3"' in dockerfile
    assert "pydantic-settings" in dockerfile
    # the system-pip form must NOT also appear — only one pinning command should run
    assert "pip install --no-cache-dir --upgrade --force-reinstall" not in dockerfile


def test_render_dockerfile_installs_sandbox_tools_via_system_pip_for_plain_pip_repos() -> None:
    dockerfile = render_dockerfile(_spec(), "v2")
    assert "pip install --no-cache-dir pytest pytest-json-report" in dockerfile


def test_render_dockerfile_installs_sandbox_tools_via_uv_for_uv_repos() -> None:
    # docs/decisions.md D27: pytest-json-report installed via system pip is just as
    # invisible to `uv run --no-sync` as pydantic was — pytest then rejects
    # --json-report as an unrecognized argument since the plugin was never in ITS
    # environment. Must land in the SAME .venv the pydantic pin targets.
    dockerfile = render_dockerfile(_spec(install_cmd=("uv", "sync", "--group", "test")), "v2")
    assert (
        "uv pip install --python /repo-base/.venv/bin/python pytest pytest-json-report"
        in dockerfile
    )
    assert "pip install --no-cache-dir pytest pytest-json-report" not in dockerfile


def test_sandbox_tools_cmd_precedes_install_cmd_creating_the_venv() -> None:
    # for a uv repo, `.venv` doesn't exist until `{install_cmd}` (`uv sync`) creates it —
    # the sandbox-tools and pydantic-pin steps must run AFTER it, not before.
    dockerfile = render_dockerfile(_spec(install_cmd=("uv", "sync", "--group", "test")), "v2")
    assert dockerfile.index("uv sync --group test") < dockerfile.index("pytest pytest-json-report")
