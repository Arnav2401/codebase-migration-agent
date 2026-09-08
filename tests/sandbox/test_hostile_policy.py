"""Phase 7a: every hardening flag must be present under the DEFAULT policy.

These assert the default explicitly, not a hand-constructed hardened policy, because that
distinction is exactly where the real gap was: `--network none` was only emitted for
`network="none"`, while every production caller uses `SandboxPolicy()` (which defaults to
`"build-only"`), so untrusted code ran with Docker's bridge network for the project's whole
history. A test that passed `network="none"` explicitly had been reporting that as covered
(docs/decisions.md D97).
"""

from pathlib import Path

import pytest

from pmigrate.sandbox.policy import build_build_args, build_run_args
from pmigrate.types import SandboxPolicy


def _default_run_args(tmp_path: Path) -> list[str]:
    return build_run_args(
        SandboxPolicy(),  # the default -- the policy the harness actually uses
        image_tag="img:v2",
        output_dir=tmp_path / "out",
        overlay_dir=tmp_path / "overlay",
        command=["pytest"],
        container_name="c",
    )


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--network", "none"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges"),
        ("--pids-limit", "512"),
        ("--cpus", "2.0"),
    ],
)
def test_default_policy_emits_each_hardening_flag(tmp_path: Path, flag: str, value: str) -> None:
    args = _default_run_args(tmp_path)
    assert flag in args, f"{flag} missing from the DEFAULT policy"
    assert args[args.index(flag) + 1] == value


def test_default_policy_is_read_only_and_non_root(tmp_path: Path) -> None:
    args = _default_run_args(tmp_path)
    assert "--read-only" in args
    assert "--user" in args
    assert args[args.index("--user") + 1] != "0:0"


def test_build_only_still_means_no_network_at_run_time(tmp_path: Path) -> None:
    """The regression that motivated D97: "build-only" grants network to the BUILD stage,
    never to the stage where untrusted code executes."""
    args = build_run_args(
        SandboxPolicy(network="build-only"),
        image_tag="img:v2",
        output_dir=tmp_path / "out",
        overlay_dir=tmp_path / "overlay",
        command=["pytest"],
        container_name="c",
    )
    assert args[args.index("--network") + 1] == "none"


def test_the_build_stage_keeps_its_network(tmp_path: Path) -> None:
    """Dependency installs need it, and nothing untrusted executes during build beyond
    installing declared dependencies."""
    assert "--network" not in build_build_args(dockerfile_dir=tmp_path, image_tag="img:v2")


def test_overlay_is_mounted_read_only_and_nothing_else_is_bound(tmp_path: Path) -> None:
    """ "No bind mounts outside the run directory" -- checked by asserting every -v argument
    points inside the run's own tmp_path."""
    args = _default_run_args(tmp_path)
    mounts = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
    assert any(m.endswith(":ro") for m in mounts), "overlay must be mounted read-only"
    for mount in mounts:
        host_path = mount.split(":")[0]
        assert str(tmp_path.resolve()) in host_path, f"unexpected bind mount: {mount}"


def test_no_docker_socket_is_ever_mounted(tmp_path: Path) -> None:
    """A mounted docker socket is a full host escape; it must never appear."""
    assert "docker.sock" not in " ".join(_default_run_args(tmp_path))
