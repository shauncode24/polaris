"""Pins how skill evidence turns into a confidence number and a label.
These numbers were captured from the code before the confidence modules
were merged, so they guard the merge against changing any score.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.evidence.scoring import (
    CONFIDENCE_CAP,
    compute_corroboration_count,
    compute_decayed_skill_confidence,
    compute_skill_confidence,
)
from app.services.evidence.scoring import (
    gap_label_for_confidence,
    label_for_confidence,
    medium_floor,
)
from app.services.evidence.scoring import decay_multiplier

NOW = datetime.now(timezone.utc)


def evidence(source_type, weight, days_old):
    return SimpleNamespace(source_type=source_type, weight=weight, created_at=NOW - timedelta(days=days_old))


def test_confidence_is_the_capped_sum_of_weights():
    assert compute_skill_confidence([0.35, 0.30, 0.25]) == pytest.approx(0.90)
    assert compute_skill_confidence([0.5, 0.5]) == CONFIDENCE_CAP == 0.97


@pytest.mark.parametrize(
    "days_old, multiplier",
    [(0, 1.0), (90, 1.0), (91, 0.85), (180, 0.85), (181, 0.65), (365, 0.65),
     (366, 0.5), (730, 0.5), (731, 0.35), (2000, 0.35)],
)
def test_evidence_loses_weight_as_it_ages(days_old, multiplier):
    assert decay_multiplier(NOW - timedelta(days=days_old)) == multiplier


def test_evidence_without_a_timestamp_counts_as_fresh():
    assert decay_multiplier(None) == 1.0


def test_a_single_fresh_project_scores_its_weight():
    assert compute_decayed_skill_confidence([evidence("project", 0.35, 10)]) == pytest.approx(0.35)


def test_two_different_source_types_earn_the_corroboration_bonus():
    score = compute_decayed_skill_confidence([evidence("project", 0.35, 10), evidence("github", 0.30, 10)])
    assert score == pytest.approx(0.7475)


def test_repeating_one_source_type_earns_no_bonus():
    score = compute_decayed_skill_confidence([evidence("project", 0.35, 10), evidence("project", 0.35, 10)])
    assert score == pytest.approx(0.70)


def test_old_evidence_is_discounted():
    assert compute_decayed_skill_confidence([evidence("project", 0.35, 400)]) == pytest.approx(0.175)


def test_the_cap_applies_after_the_bonus():
    score = compute_decayed_skill_confidence([evidence("project", 0.9, 1), evidence("github", 0.9, 1)])
    assert score == CONFIDENCE_CAP


def test_corroboration_counts_distinct_source_types():
    rows = [evidence("project", 1, 1), evidence("project", 1, 1), evidence("github", 1, 1)]
    assert compute_corroboration_count(rows) == 2


@pytest.mark.parametrize(
    "score, label",
    [(0.0, "low"), (0.29, "low"), (0.3, "medium"), (0.59, "medium"), (0.6, "high"), (0.97, "high")],
)
def test_confidence_labels(score, label):
    assert label_for_confidence(score) == label


def test_skill_gap_labels_follow_the_same_cutoffs():
    assert [gap_label_for_confidence(s) for s in (0.1, 0.4, 0.9)] == ["missing", "partial", "have"]
    assert medium_floor() == 0.3
