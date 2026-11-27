"""How LeetCode topic counts become proof of data structures and algorithms."""
import pytest

from app.services.evidence.scoring import label_for_confidence, practice_weight
from app.services.leetcode.leetcode_taxonomy import PRACTICE_TAGS, practice_by_skill


def test_no_tag_counts_toward_both_skills():
    assert not PRACTICE_TAGS["data_structures"] & PRACTICE_TAGS["algorithms"]


def test_topics_are_split_between_the_two_skills_most_practised_first():
    practice = practice_by_skill({"array": 10, "tree": 25, "greedy": 7, "database": 90, "stack": 0})

    assert practice["data_structures"].topics == [("tree", 25), ("array", 10)]
    assert practice["data_structures"].problems == 35
    assert practice["algorithms"].topics == [("greedy", 7)]


def test_names_typed_by_hand_are_understood_and_not_counted_twice():
    practice = practice_by_skill({
        "Dynamic Programming": 12, "dynamic-programming": 10, "Arrays": 8, "hash_table": 4, "Binary Search": 5,
    })

    assert practice["algorithms"].topics == [("dynamic-programming", 12), ("binary-search", 5)]
    assert practice["data_structures"].topics == [("array", 8), ("hash-table", 4)]


def test_problems_carrying_several_tags_cannot_exceed_the_number_solved():
    counts = {"array": 60, "string": 50, "hash-table": 40}

    assert practice_by_skill(counts)["data_structures"].problems == 150
    assert practice_by_skill(counts, total_solved=80)["data_structures"].problems == 80


def test_only_topics_with_a_few_solves_count_toward_breadth():
    practice = practice_by_skill({"array": 3, "string": 2, "tree": 30})["data_structures"]

    assert practice.breadth == 2


@pytest.mark.parametrize("problems,topics,label", [
    (100, 5, "high"),
    (400, 12, "high"),
    (99, 12, "medium"),   # not enough problems
    (400, 4, "medium"),   # not enough variety
    (30, 3, "medium"),
    (29, 8, "low"),
    (200, 2, "low"),      # one or two topics, however deep, is not the skill
])
def test_how_much_practice_it_takes(problems, topics, label):
    assert label_for_confidence(practice_weight(problems, topics)) == label


def test_no_practice_is_no_evidence_and_any_practice_is_some():
    assert practice_weight(0, 0) == 0
    assert practice_weight(1, 0) > 0
