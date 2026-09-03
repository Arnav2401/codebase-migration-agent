import pytest

from pmigrate.eval.stats import bootstrap_mean_ci


def test_bootstrap_mean_ci_point_estimate_is_the_plain_mean() -> None:
    result = bootstrap_mean_ci([0.0, 0.5, 1.0])
    assert result.point_estimate == pytest.approx(0.5)
    assert result.n == 3


def test_bootstrap_mean_ci_collapses_to_the_point_estimate_for_a_single_value() -> None:
    result = bootstrap_mean_ci([0.7])
    assert result.point_estimate == 0.7
    assert result.ci_low == 0.7
    assert result.ci_high == 0.7
    assert result.n == 1


def test_bootstrap_mean_ci_interval_contains_the_point_estimate() -> None:
    result = bootstrap_mean_ci([0.1, 0.9, 0.2, 0.8, 0.5, 0.6, 0.3])
    assert result.ci_low <= result.point_estimate <= result.ci_high


def test_bootstrap_mean_ci_is_narrow_for_identical_values() -> None:
    # zero true variance -- every resample mean is exactly the same value, so the
    # interval should collapse to (near) a point, not a spuriously wide range.
    result = bootstrap_mean_ci([0.5] * 20)
    assert result.ci_low == pytest.approx(0.5)
    assert result.ci_high == pytest.approx(0.5)


def test_bootstrap_mean_ci_is_wider_for_more_spread_out_values() -> None:
    tight = bootstrap_mean_ci([0.49, 0.5, 0.51] * 10, seed=1)
    spread = bootstrap_mean_ci([0.0, 0.5, 1.0] * 10, seed=1)
    assert (spread.ci_high - spread.ci_low) > (tight.ci_high - tight.ci_low)


def test_bootstrap_mean_ci_is_deterministic_for_a_fixed_seed() -> None:
    values = [0.1, 0.4, 0.6, 0.9, 0.3]
    first = bootstrap_mean_ci(values, seed=42)
    second = bootstrap_mean_ci(values, seed=42)
    assert first == second


def test_bootstrap_mean_ci_differs_across_seeds() -> None:
    values = [0.1, 0.4, 0.6, 0.9, 0.3, 0.2, 0.8]
    first = bootstrap_mean_ci(values, seed=1, n_resamples=200)
    second = bootstrap_mean_ci(values, seed=2, n_resamples=200)
    assert first.ci_low != second.ci_low or first.ci_high != second.ci_high


def test_bootstrap_mean_ci_raises_on_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        bootstrap_mean_ci([])


def test_bootstrap_mean_ci_respects_a_narrower_confidence_level() -> None:
    values = [0.1, 0.4, 0.6, 0.9, 0.3, 0.2, 0.8, 0.5]
    wide = bootstrap_mean_ci(values, confidence=0.95, seed=7)
    narrow = bootstrap_mean_ci(values, confidence=0.50, seed=7)
    assert (narrow.ci_high - narrow.ci_low) <= (wide.ci_high - wide.ci_low)
