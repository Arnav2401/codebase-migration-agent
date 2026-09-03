"""Regression test for docs/phase-4-triage.md's acceptance criterion: classifier accuracy
>=85% on >=100 hand-labelled real failures. docs/decisions.md D55/D56.

Deliberately does NOT trust `LabelledFailure.predicted_cls` as stored in
`tests/fixtures/triage/labelled_dev.jsonl` -- that field is a snapshot of whatever the
classifier said the moment each entry was labelled, and would silently go stale the next
time `triage/rules.py` changes, making this test meaningless as a regression check. Instead
this re-classifies every entry FRESH through the real `RuleBasedClassifier` (the same
public `Classifier` protocol `agent/graph.py` uses) against real baseline data (from
`corpus/manifest.json`) and compares against `true_cls`, which is the one thing in this
fixture that's actually permanent -- a human's real judgment, not the classifier's own
output at some point in the past.
"""

from pathlib import Path

from pmigrate.corpus.manifest_io import load_manifest
from pmigrate.eval.metrics import classifier_accuracy
from pmigrate.triage.classifier import RuleBasedClassifier
from pmigrate.triage.label import LabelledFailure, load_labelled
from pmigrate.types import TestOutcome, TestRun

FIXTURE = Path(__file__).parent.parent / "fixtures" / "triage" / "labelled_dev.jsonl"
REPO_ROOT = Path(__file__).parent.parent.parent


def _reclassify_fresh(labelled: list[LabelledFailure]) -> list[LabelledFailure]:
    baselines = {
        s.repo_id: s.baseline for s in load_manifest(REPO_ROOT / "corpus" / "manifest.json")
    }
    classifier = RuleBasedClassifier()
    fresh = []
    for lf in labelled:
        # a collection error (no node_id) travels through TestRun.collection_errors, not
        # .outcomes -- matches how collect_raw_failures builds RawFailures for real, and
        # matters here because PREEXISTING only ever applies to a real node_id.
        if lf.node_id is None:
            run = TestRun(
                outcomes=(),
                collection_errors=(lf.text,),
                exit_code=1,
                duration_s=0.0,
                truncated=False,
            )
        else:
            run = TestRun(
                outcomes=(TestOutcome(lf.node_id, "failed", 0.0, None, lf.text, None),),
                collection_errors=(),
                exit_code=1,
                duration_s=0.0,
                truncated=False,
            )
        diagnoses = classifier.classify(run, baselines.get(lf.repo_id))
        # exactly one raw failure in, so exactly one diagnosis out.
        cls = diagnoses[0].cls
        fresh.append(
            LabelledFailure(
                repo_id=lf.repo_id,
                node_id=lf.node_id,
                predicted_cls=cls,
                true_cls=lf.true_cls,
                text=lf.text,
            )
        )
    return fresh


def test_classifier_accuracy_meets_the_phase_4_acceptance_threshold() -> None:
    if not FIXTURE.exists():
        return  # nothing labelled yet -- see `pmigrate triage label`; not a failure, just N/A
    labelled = load_labelled(FIXTURE)
    assert len(labelled) >= 100, "phase-4-triage.md requires >=100 hand-labelled real failures"

    fresh = _reclassify_fresh(labelled)
    accuracy = classifier_accuracy(fresh)
    assert accuracy >= 0.85, (
        f"classifier_accuracy={accuracy:.3f} is below phase-4-triage.md's 0.85 threshold "
        f"on {len(fresh)} hand-labelled real failures"
    )
