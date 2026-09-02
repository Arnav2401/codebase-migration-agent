"""Build and cache Docker images per (repo, sha, deps-hash, pydantic version)
(docs/interfaces.md §3, docs/phase-2-sandbox.md "Image caching").

Verified against a live Docker daemon on 2026-09-01 (docs/phase-2-sandbox.md's acceptance
criteria) against `pytest-dev/pytest-mock` (standing in for a real corpus repo — Phase 0's
corpus is still empty) and a throwaway hostile-fixture repo. Cache-hit overhead measured at
0.03s. Two real bugs were found and fixed during that verification pass, not before: the original
`cp -a` in the entrypoint script failed under the non-root sandbox user (it tries to
preserve ownership/timestamps it isn't permitted to set on the tmpfs), silently aborting
every container under `set -e` — see docs/decisions.md D14. And the deps hash didn't
originally cover the Dockerfile/entrypoint template content itself, so fixing D14 and
rebuilding would have kept serving the old broken image under the same tag — fixed by
folding the template strings into `compute_deps_hash` below.

A third real bug, found against an actual corpus repo (`madkote/fastapi-plugins`) rather
than a throwaway fixture: pinning pydantic BEFORE `{install_cmd}` runs put a direct,
mathematically unsatisfiable constraint in front of pip's resolver — the repo's own
`setup.py` (at `pre_sha`, correctly) declares `pydantic<2.0.0`, which can never be
satisfied alongside a pre-installed `pydantic>=2`. Pip's resolver doesn't detect this as
impossible; it backtracks through dozens of `fastapi` versions hunting for a combination
that satisfies both, and never finishes — this is what silently ate the full 30-minute
`BUILD_TIMEOUT_S` on the first real end-to-end run, not a slow build. Fixed by installing
the repo's own dependencies FIRST (whatever pydantic version it naturally wants), then
force-reinstalling the target pydantic version afterward as a separate, non-resolving step
(`--force-reinstall`, no dependency re-resolution) — deliberately overriding what the repo
asked for rather than asking pip to reconcile both.

Cache key, honestly approximated: docs/phase-2-sandbox.md says the key is
`repo_id + sha + hash(dependency files) + pydantic_version`. Hashing the actual dependency
file *content* would mean cloning the repo before deciding whether a build is even needed
— backwards. Since `sha` already pins the dependency files' content (the same commit always
has the same requirements.txt), what's actually left to vary independently of `sha` is the
Python-level configuration we control: `install_cmd`, `setup_overrides`, `python_version`.
Hashing THOSE is what `compute_deps_hash` does — functionally equivalent for a fixed sha,
and it correctly busts the cache if you tweak `setup_overrides` in the manifest without
touching the commit (a real scenario during Phase 0 corpus curation).

A fourth real bug, found via a canary edit against `SupImDos__pydantic-argparse` (a
`src/`-layout repo) rather than assumed: `{install_cmd}`'s editable install
(`pip install -e .`) bakes the absolute build-time path `/repo-base/src` into site-packages
(a `.pth` file, or a PEP 660 finder module for repos where setuptools picks that strategy
instead), so every import resolved against the read-only `/repo-base` reference copy no
matter what the entrypoint later copied into the writable `/repo` tmpfs — the overlay
mechanism had zero effect on what actually got tested for any `src/`-layout repo. Confirmed
with `raise RuntimeError(...)` swapped into the overlay's copy of the package's
`__init__.py`: the test run still failed with the ORIGINAL code's error, and the traceback's
frames were `/repo-base`-absolute, not `/repo`-relative. See docs/decisions.md D44/D45.
Fixed by `FIX_EDITABLE_PATHS_SCRIPT` below, run once at build time (root, writable) rather
than in the entrypoint (non-root, `--read-only` root — site-packages isn't writable there).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pmigrate.sandbox.policy import BUILD_PLATFORM, build_build_args
from pmigrate.types import ImageRef, RepoSpec

BUILD_TIMEOUT_S = 30 * 60  # matches docs/phase-0-corpus.md's per-repo debugging cap

ENTRYPOINT_SCRIPT = """#!/bin/sh
set -e
# NOT `cp -a`: archive mode tries to preserve ownership/timestamps, which the non-root
# sandbox user (policy.py's NOBODY_UID_GID) isn't permitted to do on a tmpfs it doesn't
# own — that failure is silent-looking but non-zero, and `set -e` aborts the container
# before pytest ever runs. Found against a live Docker daemon, not assumed — see
# docs/decisions.md D14. `-r` copies contents without trying to preserve metadata we don't
# need anyway.
cp -r /repo-base/. /repo/
if [ -d /overlay ] && [ -n "$(ls -A /overlay 2>/dev/null)" ]; then
    cp -r /overlay/. /repo/
fi
cd /repo
exec "$@"
"""

FIX_EDITABLE_PATHS_SCRIPT = '''\
"""Rewrite absolute paths baked in by editable installs (pip/uv `-e`) so imports resolve
against the container's writable /repo tmpfs at runtime instead of the read-only
/repo-base reference copy baked in at image-build time. See docs/decisions.md D44/D45.

PEP 660 editable installs record the absolute source directory as it existed at install
time -- here, always /repo-base (this Dockerfile's WORKDIR) -- either as a literal path
inside a `.pth` file (setuptools' "compat" mode) or as string literals inside a generated
`__editable__*_finder.py` module (the "strict" mode). Either way that's baked into the
read-only image layer and never revisited, so it keeps pointing at /repo-base even after
the entrypoint (image.py's ENTRYPOINT_SCRIPT) copies /repo-base into the writable /repo
tmpfs and layers the agent's overlay edits on top. Fix: textually rewrite every occurrence
of the literal string "/repo-base" to "/repo" in every text file under every site-packages
directory this image's Python(s) actually use -- covers both mechanisms uniformly, since
both simply embed that absolute path as a string, and needs no per-mode detection logic.

Runs once at image-build time (root, writable filesystem) rather than in the entrypoint
(non-root, --read-only container root -- site-packages isn't writable there at all).
"""
import glob
from pathlib import Path

try:
    import site

    SEARCH_ROOTS = [Path(p) for p in site.getsitepackages()]
except AttributeError:
    SEARCH_ROOTS = []
SEARCH_ROOTS += [Path(p) for p in glob.glob("/repo-base/.venv/lib/python*/site-packages")]

REPLACE_FROM = b"/repo-base"
REPLACE_TO = b"/repo"

for root in SEARCH_ROOTS:
    if not root.is_dir():
        continue
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\\x00" in data:
            continue  # binary file -- a length-changing replace could corrupt it; skip
        if REPLACE_FROM not in data:
            continue
        try:
            path.write_bytes(data.replace(REPLACE_FROM, REPLACE_TO))
        except OSError:
            continue
'''

DOCKERFILE_TEMPLATE = """\
FROM python:{python_version}-slim
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo-base
RUN git clone --quiet {url} . && git checkout --quiet {sha}
{setup_overrides}
RUN pip install --no-cache-dir uv
RUN {install_cmd}
RUN {sandbox_tools_cmd}
RUN {pydantic_pin_cmd}
COPY fix_editable_paths.py /fix_editable_paths.py
RUN python3 /fix_editable_paths.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
"""


def pydantic_constraint(version: Literal["v1", "v2"]) -> str:
    return "<2,>=1.9" if version == "v1" else ">=2,<3"


def extra_packages(version: Literal["v1", "v2"]) -> str:
    """`pydantic-settings` is a separate package in v2 — installed unconditionally here
    rather than left to `install_cmd`/codemod rules, since virtually every real migration
    needs it (BaseSettings moved out of pydantic core) and `basesettings_import.py`'s own
    codemod deliberately does not touch dependency files (see its module docstring). Found
    the gap live: rewriting `pydantic.BaseSettings` -> `pydantic_settings.BaseSettings` is
    correct, but `ModuleNotFoundError: No module named 'pydantic_settings'` is exactly what
    you get if nothing ever installs the package it now imports."""
    return "pydantic-settings" if version == "v2" else ""


def venv_install_cmd(
    packages: str,
    install_cmd: tuple[str, ...],
    *,
    force_reinstall: bool,
    workdir: str = "/repo-base",
) -> str:
    """Docs/decisions.md D27: `install_cmd` isn't always plain pip into the system
    Python — a `uv`-based repo (`uv sync ...`) installs into an isolated `.venv` it
    manages itself, which a plain system `pip install` would silently miss entirely (it
    would "succeed" while installing into the WRONG Python — the one `uv run pytest`
    never uses). Detected from `install_cmd[0]` rather than a new RepoSpec field:
    `install_cmd` already fully determines which install ecosystem a repo uses, so its
    first token is a legitimate, already-present signal rather than data duplicated into
    a second field.

    Shared by both the sandbox's own test tooling (pytest/pytest-json-report) and the
    pydantic version pin — found live that fixing only the pydantic case wasn't enough:
    `pytest-json-report`, installed via system pip exactly like pydantic originally was,
    is equally invisible to `uv run --no-sync`, and `pytest` itself then rejects
    `--json-report` as an unrecognized argument since the plugin was never in ITS
    environment either.

    `workdir` defaults to `/repo-base` (this module's own `WORKDIR`) but is a real
    parameter, not a hardcoded assumption — found live (D31) that reusing this function
    as-is from `corpus/capture_baselines.py`, whose Dockerfile clones into `/repo` instead,
    silently pointed `uv pip install --python` at a `.venv` that was never created there.
    """
    if install_cmd and install_cmd[0] == "uv":
        flag = "--upgrade --force-reinstall " if force_reinstall else ""
        return f"uv pip install --python {workdir}/.venv/bin/python {flag}{packages}".strip()
    flag = "--upgrade --force-reinstall " if force_reinstall else ""
    return f"pip install --no-cache-dir {flag}{packages}".strip()


def sandbox_tools_cmd(install_cmd: tuple[str, ...], *, workdir: str = "/repo-base") -> str:
    return venv_install_cmd(
        "pytest pytest-json-report", install_cmd, force_reinstall=False, workdir=workdir
    )


def pydantic_pin_cmd(
    pydantic_constraint: str,
    extra_packages: str,
    install_cmd: tuple[str, ...],
    *,
    workdir: str = "/repo-base",
) -> str:
    packages = f'"pydantic{pydantic_constraint}" {extra_packages}'.strip()
    return venv_install_cmd(packages, install_cmd, force_reinstall=True, workdir=workdir)


def compute_deps_hash(repo: RepoSpec) -> str:
    # Includes DOCKERFILE_TEMPLATE/ENTRYPOINT_SCRIPT/BUILD_PLATFORM themselves, not just
    # per-repo fields — found the hard way (verified against a live daemon) that editing
    # the entrypoint script without this would leave stale cached images silently served
    # under the same tag, since nothing about the template's own content otherwise fed
    # into the hash. BUILD_PLATFORM joined the same list for the same reason
    # (docs/decisions.md D27): pinning it after images already existed under the host's
    # native arch would otherwise let those old, wrong-platform images keep matching
    # their tag forever.
    payload = json.dumps(
        {
            "install_cmd": repo.install_cmd,
            "setup_overrides": repo.setup_overrides,
            "python_version": repo.python_version,
            "dockerfile_template": DOCKERFILE_TEMPLATE,
            "entrypoint_script": ENTRYPOINT_SCRIPT,
            "fix_editable_paths_script": FIX_EDITABLE_PATHS_SCRIPT,
            "build_platform": BUILD_PLATFORM,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def image_tag(repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> str:
    return (
        f"pmigrate-sandbox:{repo.repo_id}-{repo.pre_sha[:8]}-{pydantic}-{compute_deps_hash(repo)}"
    )


def render_dockerfile(repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> str:
    return DOCKERFILE_TEMPLATE.format(
        python_version=repo.python_version,
        url=repo.url,
        sha=repo.pre_sha,
        setup_overrides="\n".join(repo.setup_overrides),
        install_cmd=" ".join(repo.install_cmd),
        sandbox_tools_cmd=sandbox_tools_cmd(repo.install_cmd),
        pydantic_pin_cmd=pydantic_pin_cmd(
            pydantic_constraint(pydantic), extra_packages(pydantic), repo.install_cmd
        ),
    )


def _image_exists(tag: str) -> bool:
    result = subprocess.run(["docker", "image", "inspect", tag], capture_output=True, timeout=30)
    return result.returncode == 0


def build_image(repo: RepoSpec, pydantic: Literal["v1", "v2"]) -> ImageRef:
    """Always builds from `repo.pre_sha` — the agent edits from there via an overlay
    (policy.py) regardless of which pydantic version is pinned into the image; there is
    no separate "post_sha" sandbox use case here (that's Phase 0's baseline-capture
    concern, a narrower standalone script — see capture_baselines.py)."""
    tag = image_tag(repo, pydantic)
    ref = ImageRef(
        tag=tag,
        repo_id=repo.repo_id,
        sha=repo.pre_sha,
        pydantic=pydantic,
        deps_hash=compute_deps_hash(repo),
        test_cmd=repo.test_cmd,
    )

    if _image_exists(tag):
        return ref  # cache hit — docs/phase-2-sandbox.md acceptance: <10s overhead

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "Dockerfile").write_text(render_dockerfile(repo, pydantic))
        (tmp_path / "entrypoint.sh").write_text(ENTRYPOINT_SCRIPT)
        (tmp_path / "fix_editable_paths.py").write_text(FIX_EDITABLE_PATHS_SCRIPT)
        args = build_build_args(dockerfile_dir=tmp_path, image_tag=tag)
        subprocess.run(args, check=True, capture_output=True, timeout=BUILD_TIMEOUT_S)

    return ref
