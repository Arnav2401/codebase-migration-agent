"""Turns a SandboxPolicy (docs/interfaces.md §3) into the actual `docker run` argument
list. Pure and fully testable by asserting on the produced flags — no Docker needed to
check that a policy of network="none" actually produces `--network none`.

The overlay mechanism (docs/phase-2-sandbox.md: "mounts the repo read-only, agent edits
applied as a writable overlay... a run can never corrupt the corpus checkout") is built
from ordinary Docker primitives rather than literal OverlayFS syscalls:
  - the image bakes the repo into `/repo-base` (read-only reference, never touched again)
  - the container root is `--read-only`; the actual working copy lives in a `--tmpfs /repo`
    (RAM-backed, destroyed with the container — this is what makes read_only_root=True
    compatible with pytest needing to write __pycache__/.pytest_cache/etc.)
  - image.py's entrypoint script copies `/repo-base` into `/repo`, then copies the
    host-supplied overlay directory (bind-mounted read-only at `/overlay`) on top,
    before invoking pytest — so edits land in the tmpfs copy, never in the image layers
    or the host's corpus checkout
This means read_only_root is enforced literally: nothing docker writes here ever survives
past `--rm`, and the corpus checkout on the host is never opened for writing at all.
"""

from __future__ import annotations

from pathlib import Path

from pmigrate.types import SandboxPolicy

NOBODY_UID_GID = "65534:65534"  # conventional cross-distro "nobody" — no /etc/passwd entry needed
REPO_TMPFS_PATH = "/repo"
OVERLAY_MOUNT_PATH = "/overlay"
OUTPUT_MOUNT_PATH = "/out"
# Pinned rather than left to the host's native arch (docs/decisions.md D27): a build on
# this Apple Silicon Mac defaults to linux/arm64, and a real corpus repo's `uv.lock`
# (plugboard-dev/plugboard) pinned `greenlet==3.4.0`, which ships NO Linux ARM64 wheel at
# all — only x86_64/musllinux/macOS/Windows. The failure is purely "which machine built
# this image," which is exactly what PLAN.md's I6 ("every scored run is reproducible")
# exists to rule out. x86_64 chosen as the target since it's what the corpus repo's own
# wheel coverage (and most CI) actually supports; QEMU emulation makes builds slower on
# an ARM host but that's a real cost worth paying for a build that behaves the same
# regardless of who runs it.
BUILD_PLATFORM = "linux/amd64"


def _repo_tmpfs_size_mb(policy: SandboxPolicy) -> int:
    # the working copy of the repo lives here, so it needs real headroom, but never more
    # than half the container's total memory budget.
    return max(256, policy.memory_mb // 2)


def build_run_args(
    policy: SandboxPolicy,
    *,
    image_tag: str,
    output_dir: Path,
    overlay_dir: Path | None,
    command: list[str],
    container_name: str,
) -> list[str]:
    """`container_name` is required, not optional: verified against a live daemon that
    killing the `docker run` CLI process on a Python-level timeout does NOT stop the
    container it's managing — the daemon keeps it running orphaned, still burning CPU,
    with no way to reach it again except by name or ID. runner.py force-kills by this
    name in its timeout handler; see docs/decisions.md D13. `--platform` is pinned
    explicitly (matching build_build_args) rather than relying on Docker inferring it
    from the image's own manifest — explicit here is one less thing to get wrong."""
    args: list[str] = [
        "docker",
        "run",
        "--rm",
        "--platform",
        BUILD_PLATFORM,
        "--name",
        container_name,
    ]

    if policy.read_only_root:
        args.append("--read-only")
        args += ["--tmpfs", f"{REPO_TMPFS_PATH}:rw,exec,size={_repo_tmpfs_size_mb(policy)}m"]

    for path in policy.tmpfs:
        if path == REPO_TMPFS_PATH:
            continue  # already mounted above with its own size, don't double-mount
        args += ["--tmpfs", f"{path}:rw,size=256m"]

    args += ["-v", f"{output_dir.resolve()}:{OUTPUT_MOUNT_PATH}"]
    if overlay_dir is not None:
        args += ["-v", f"{overlay_dir.resolve()}:{OVERLAY_MOUNT_PATH}:ro"]

    if policy.network == "none":
        args += ["--network", "none"]

    args += ["--memory", f"{policy.memory_mb}m", "--memory-swap", f"{policy.memory_mb}m"]
    args += ["--cpus", str(policy.cpus)]
    args += ["--pids-limit", str(policy.pids_limit)]
    args += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
    args += ["--user", NOBODY_UID_GID]

    args.append(image_tag)
    args += command
    return args


def build_build_args(*, dockerfile_dir: Path, image_tag: str) -> list[str]:
    """Build stage — network stays on (dependency installs need it); no hardening flags,
    since nothing untrusted executes here beyond `pip install` against declared deps.
    `--platform` is pinned (see BUILD_PLATFORM above) rather than left to the host."""
    return [
        "docker",
        "build",
        "--platform",
        BUILD_PLATFORM,
        "-t",
        image_tag,
        str(dockerfile_dir.resolve()),
    ]
