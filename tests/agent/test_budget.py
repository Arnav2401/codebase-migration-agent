import time

from pmigrate.agent.budget import BudgetState, NoProgressDetector, failure_signature


def test_no_breach_when_under_all_caps() -> None:
    state = BudgetState(usd_spent=1.0, usd_cap=5.0, iterations=1, max_iterations=20)
    assert state.exceeded() is None


def test_usd_cap_breach() -> None:
    state = BudgetState(usd_spent=6.0, usd_cap=5.0)
    assert state.exceeded() == "usd_cap"


def test_max_iterations_breach() -> None:
    state = BudgetState(iterations=21, max_iterations=20)
    assert state.exceeded() == "max_iterations"


def test_wallclock_breach() -> None:
    state = BudgetState(started_at=time.time() - 100, wallclock_cap_s=10)
    assert state.exceeded() == "wallclock_cap"


def test_spend_accumulates_and_is_immutable() -> None:
    state = BudgetState()
    new_state = state.spend(usd=1.5, tokens_in=100, tokens_out=50)
    assert new_state.usd_spent == 1.5
    assert new_state.tokens_in == 100
    assert new_state.tokens_out == 50
    assert state.usd_spent == 0.0  # original untouched


def test_spend_is_cumulative_across_calls() -> None:
    state = BudgetState().spend(usd=1.0).spend(usd=2.0)
    assert state.usd_spent == 3.0


def test_next_iteration_increments() -> None:
    state = BudgetState().next_iteration().next_iteration()
    assert state.iterations == 2


# --- no-progress detector -----------------------------------------------------------


def test_failure_signature_is_order_independent() -> None:
    assert failure_signature(["b", "a"]) == failure_signature(["a", "b"])


def test_failure_signature_differs_for_different_sets() -> None:
    assert failure_signature(["a"]) != failure_signature(["a", "b"])


def test_detector_does_not_trigger_on_first_observation() -> None:
    detector = NoProgressDetector()
    assert detector.observe(["test_a", "test_b"]) is False


def test_detector_triggers_when_same_failures_recur() -> None:
    detector = NoProgressDetector(repeat_threshold=2)
    assert detector.observe(["test_a", "test_b"]) is False
    assert detector.observe(["test_a", "test_b"]) is True


def test_detector_resets_on_progress() -> None:
    detector = NoProgressDetector(repeat_threshold=2)
    assert detector.observe(["test_a", "test_b"]) is False
    assert detector.observe(["test_a"]) is False  # progress — one test now passes
    assert detector.observe(["test_a"]) is True  # stuck again, but on the new smaller set


def test_detector_custom_threshold() -> None:
    detector = NoProgressDetector(repeat_threshold=3)
    assert detector.observe(["test_a"]) is False
    assert detector.observe(["test_a"]) is False
    assert detector.observe(["test_a"]) is True


def test_detector_reset_clears_state() -> None:
    detector = NoProgressDetector(repeat_threshold=2)
    detector.observe(["test_a"])
    detector.reset()
    assert detector.observe(["test_a"]) is False
