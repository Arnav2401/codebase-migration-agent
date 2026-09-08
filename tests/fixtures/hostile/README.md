# Hostile fixture

Runs *inside* the sandbox and asserts the container's own confinement. A green run here is
evidence the Phase 7a policy holds; a red one names the control that gave way.

Deliberately not part of `tests/` — pytest must not collect it on the host, where every
assertion would fail for the ordinary reason that a developer laptop is not a sandbox.
Exercised by `tests/sandbox/test_hostile_policy.py` (flags) and by a live Docker run.
