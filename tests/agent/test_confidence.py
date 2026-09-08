from collections import Counter

from pmigrate.agent.confidence import (
    DEFAULT_WEIGHTS,
    HARD_CLASSES,
    ConfidenceInputs,
    score,
)
from pmigrate.agent.graph import changed_lines
from pmigrate.types import FailureClass


def test_a_fully_mechanical_first_iteration_run_scores_high() -> None:
    s = score(
        ConfidenceInputs(
            mechanical_lines=100,
            model_lines=0,
            iterations=1,
            max_iterations=20,
            diagnosis_counts=Counter({FailureClass.IMPORT_ERROR: 3}),
            symbol_test_coverage=0.9,
        )
    )
    assert s.value > 0.85
    assert s.missing == ()


def test_a_model_written_many_iteration_hard_class_run_scores_low() -> None:
    s = score(
        ConfidenceInputs(
            mechanical_lines=0,
            model_lines=100,
            iterations=18,
            max_iterations=20,
            diagnosis_counts=Counter({FailureClass.VALIDATION_BEHAVIOUR: 4}),
            symbol_test_coverage=0.1,
        )
    )
    assert s.value < 0.2


def test_unmeasured_components_are_redistributed_not_scored_as_zero() -> None:
    """docs/decisions.md D92. Scoring an unmeasurable component as 0.0 would depress every
    prediction by a constant -- a different, wrong scale rather than "less confident" --
    and would make the calibration plot look well-behaved while being uniformly shifted."""
    measurable = ConfidenceInputs(
        mechanical_lines=100,
        model_lines=0,
        iterations=1,
        max_iterations=20,
        diagnosis_counts=Counter({FailureClass.IMPORT_ERROR: 1}),
        symbol_test_coverage=1.0,
    )
    without_coverage = ConfidenceInputs(
        mechanical_lines=100,
        model_lines=0,
        iterations=1,
        max_iterations=20,
        diagnosis_counts=Counter({FailureClass.IMPORT_ERROR: 1}),
        symbol_test_coverage=None,
    )
    full = score(measurable)
    partial = score(without_coverage)

    assert "symbol_coverage" in partial.missing
    # Redistribution keeps the score on the SAME SCALE: dropping a component the run
    # maxed out barely moves it. Scoring the missing one as 0.0 would instead subtract its
    # whole weight, which is the constant shift this design exists to avoid.
    zero_filled = full.value - DEFAULT_WEIGHTS["symbol_coverage"]
    assert abs(partial.value - full.value) < 0.01
    assert partial.value - zero_filled > 0.10
    assert abs(sum(partial.weights_used.values()) - 1.0) < 1e-9


def test_no_diff_leaves_mechanical_unmeasured_rather_than_zero() -> None:
    """A run that changed nothing is not "0% mechanical" -- there is no diff to judge."""
    s = score(ConfidenceInputs(mechanical_lines=0, model_lines=0, iterations=1))
    assert "mechanical" in s.missing


def test_a_green_run_leaves_class_difficulty_unmeasured() -> None:
    """No diagnoses is no evidence about difficulty, not evidence that everything was easy."""
    s = score(ConfidenceInputs(mechanical_lines=10, model_lines=0, diagnosis_counts=Counter()))
    assert "easy_classes" in s.missing


def test_hard_classes_are_the_behavioural_ones() -> None:
    """An import error either resolves or does not; a coercion change can look correct and
    be wrong, which is what the hard set is for."""
    assert FailureClass.IMPORT_ERROR not in HARD_CLASSES
    assert FailureClass.VALIDATION_BEHAVIOUR in HARD_CLASSES
    assert FailureClass.UNKNOWN in HARD_CLASSES


def test_weights_sum_to_one_so_the_score_is_a_fraction() -> None:
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_explain_names_the_redistributed_components() -> None:
    s = score(ConfidenceInputs(mechanical_lines=1, model_lines=1, iterations=1))
    assert "unmeasured, weight redistributed" in s.explain()


# --- mechanical line counting (docs/decisions.md D93) ---------------------------------


def test_changed_lines_counts_both_sides_and_skips_diff_headers() -> None:
    """Additions AND removals: replacing ten lines with ten others is twenty lines of risk,
    not zero. `+++`/`---` headers are not content."""
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-old_one\n"
        "-old_two\n"
        "+new_one\n"
        "+new_two\n"
        " unchanged\n"
    )
    assert changed_lines(diff) == 4


def test_changed_lines_of_an_empty_diff_is_zero() -> None:
    assert changed_lines("") == 0
