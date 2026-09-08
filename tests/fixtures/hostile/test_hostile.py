"""A deliberately hostile test suite (phase-2-sandbox.md, phase-7-guardrails.md 7a).

These are the things model-generated or repo-supplied test code could plausibly attempt.
Each asserts that the SANDBOX stops it, so a passing run of this file inside the container
is evidence the policy holds -- and a failing one names exactly which control gave way.
"""

import os
import socket
import subprocess


def test_network_egress_is_impossible():
    """--network none. The single most important control: it is what makes exfiltration
    unreachable regardless of what any repo comment talked the model into."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        try:
            s.connect(("1.1.1.1", 80))
        except OSError:
            return  # expected
    raise AssertionError("network egress succeeded -- --network none is not in effect")


def test_dns_resolution_is_impossible():
    """Separate from the socket test: a container can have DNS without routing, and a
    resolver leak is still an exfiltration channel."""
    try:
        socket.gethostbyname("example.com")
    except OSError:
        return
    raise AssertionError("DNS resolved -- the container has more network than intended")


def test_root_filesystem_is_read_only():
    """--read-only. Writable system paths would let a hostile suite persist across runs."""
    try:
        with open("/etc/pmigrate_probe", "w") as fh:
            fh.write("x")
    except OSError:
        return
    os.unlink("/etc/pmigrate_probe")
    raise AssertionError("wrote to /etc -- the root filesystem is not read-only")


def test_process_is_not_root():
    """--user. Combined with --cap-drop ALL this is what makes a container escape need a
    kernel bug rather than a misconfiguration."""
    assert os.geteuid() != 0, "running as root inside the sandbox"


def test_new_privileges_are_denied():
    """--security-opt no-new-privileges: a setuid binary must not gain privileges."""
    if not os.path.exists("/bin/su"):
        return  # nothing setuid to try; the flag is asserted structurally in test_policy.py
    proc = subprocess.run(["/bin/su", "-c", "id -u"], capture_output=True, text=True)
    assert proc.returncode != 0 or proc.stdout.strip() != "0"


def test_docker_socket_is_not_mounted():
    """A mounted docker socket is a full host escape, so its absence is checked directly
    rather than inferred from the run arguments."""
    assert not os.path.exists("/var/run/docker.sock")


def test_cannot_reach_the_host_filesystem():
    """No bind mounts outside the run directory: the agent's own checkout must be
    invisible from inside the container."""
    for path in ("/host", "/Users", "/home/arnavgupta"):
        assert not os.path.isdir(path), f"{path} is visible inside the sandbox"
