from pathlib import Path

from pmigrate.sandbox.policy import build_build_args, build_run_args
from pmigrate.types import SandboxPolicy


def test_network_none_produces_network_none_flag(tmp_path: Path) -> None:
    policy = SandboxPolicy(network="none")
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert "--network" in args
    assert args[args.index("--network") + 1] == "none"


def test_read_only_root_mounts_repo_as_tmpfs(tmp_path: Path) -> None:
    policy = SandboxPolicy(read_only_root=True, memory_mb=2048)
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert "--read-only" in args
    tmpfs_values = [args[i + 1] for i, a in enumerate(args) if a == "--tmpfs"]
    repo_mount = next(v for v in tmpfs_values if v.startswith("/repo:"))
    assert "rw" in repo_mount and "exec" in repo_mount
    # tmpfs size is capped at half the memory budget, never below the 256m floor
    assert "size=1024m" in repo_mount


def test_read_only_root_false_skips_repo_tmpfs(tmp_path: Path) -> None:
    policy = SandboxPolicy(read_only_root=False)
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert "--read-only" not in args
    tmpfs_values = [args[i + 1] for i, a in enumerate(args) if a == "--tmpfs"]
    assert not any(v.startswith("/repo:") for v in tmpfs_values)


def test_overlay_mounted_read_only_when_present(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    policy = SandboxPolicy()
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=out,
        overlay_dir=overlay,
        command=["pytest"],
        container_name="test-container",
    )
    mount_specs = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
    overlay_mount = next(m for m in mount_specs if m.endswith(":/overlay:ro"))
    assert str(overlay.resolve()) in overlay_mount


def test_overlay_omitted_when_none(tmp_path: Path) -> None:
    policy = SandboxPolicy()
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert not any(a.endswith(":/overlay:ro") for a in args)


def test_resource_caps_present(tmp_path: Path) -> None:
    policy = SandboxPolicy(memory_mb=1024, cpus=1.5, pids_limit=128)
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert "1024m" in args
    assert "1.5" in args
    assert "128" in args
    assert "--cap-drop" in args and "ALL" in args
    assert "--security-opt" in args and "no-new-privileges" in args
    assert "--user" in args


def test_memory_swap_matches_memory_to_disable_swap(tmp_path: Path) -> None:
    policy = SandboxPolicy(memory_mb=512)
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="test-container",
    )
    assert args[args.index("--memory") + 1] == "512m"
    assert args[args.index("--memory-swap") + 1] == "512m"


def test_command_and_image_tag_appended_last(tmp_path: Path) -> None:
    policy = SandboxPolicy()
    args = build_run_args(
        policy,
        image_tag="my-image:tag",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest", "-q", "tests/test_x.py::test_one"],
        container_name="test-container",
    )
    idx = args.index("my-image:tag")
    assert args[idx + 1 :] == ["pytest", "-q", "tests/test_x.py::test_one"]


def test_build_args_no_hardening_flags(tmp_path: Path) -> None:
    args = build_build_args(dockerfile_dir=tmp_path, image_tag="img:v1")
    assert args == [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "-t",
        "img:v1",
        str(tmp_path.resolve()),
    ]
    assert "--network" not in args
    assert "--read-only" not in args


def test_build_args_pins_platform_regardless_of_host_arch(tmp_path: Path) -> None:
    # docs/decisions.md D27: a build on this Mac (arm64) silently produced an image
    # incompatible with a real corpus repo's locked dependencies (no linux/aarch64 wheel
    # for `greenlet`). Pinning the platform explicitly makes the build the same
    # regardless of which machine runs it.
    args = build_build_args(dockerfile_dir=tmp_path, image_tag="img:v1")
    assert "--platform" in args
    assert args[args.index("--platform") + 1] == "linux/amd64"


def test_run_args_pin_the_same_platform_as_build(tmp_path: Path) -> None:
    policy = SandboxPolicy()
    args = build_run_args(
        policy,
        image_tag="img:v1",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="c1",
    )
    assert "--platform" in args
    assert args[args.index("--platform") + 1] == "linux/amd64"


def test_container_name_is_set(tmp_path: Path) -> None:
    policy = SandboxPolicy()
    args = build_run_args(
        policy,
        image_tag="img",
        output_dir=tmp_path,
        overlay_dir=None,
        command=["pytest"],
        container_name="pmigrate-run-abc123",
    )
    assert args[args.index("--name") + 1] == "pmigrate-run-abc123"
