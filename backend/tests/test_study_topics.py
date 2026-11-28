"""Which LeetCode topics bear on a skill, and which days of a plan link to them.
No model, no database.
"""
import pytest

from app.schemas.career_planner.career_plan import DailyPlanItem
from app.services.career_planner.plan_generation import _add_links
from app.services.interview.study_plan import leetcode_topics

BASE = "https://leetcode.com/tag/"


def topics(skill, names=None, counts=None):
    return [(t.topic, t.solved) for t in leetcode_topics(skill, names or {skill}, counts or {})]


def test_algorithms_get_their_least_practised_topics_first():
    counts = {"sliding-window": 4, "binary-search": 9, "greedy": 2, "backtracking": 7, "sorting": 30}

    found = topics("algorithms", counts=counts)

    assert len(found) == 5
    assert [solved for _topic, solved in found] == sorted(solved for _topic, solved in found)
    assert ("Sorting", 30) not in found and ("Binary Search", 9) not in found


def test_data_structures_start_in_the_usual_order_when_nothing_is_synced():
    assert topics("data_structures") == [
        ("Arrays & Hashing", None), ("Strings", None), ("Stack", None), ("Queue", None), ("Linked List", None)]


def test_a_topics_count_covers_all_its_tags():
    found = dict(topics("data_structures", counts={"array": 3, "hash-table": 4, "tree": 99, "graph": 99,
                                                   "string": 99, "stack": 99, "queue": 99, "linked-list": 99}))

    assert found["Arrays & Hashing"] == 7


def test_every_link_is_to_a_tag_that_bears_on_the_skill():
    links = leetcode_topics("algorithms", {"algorithms"}, {})
    graphs = leetcode_topics("data_structures", {"x"}, {t: 50 for t in (
        "array", "string", "stack", "queue", "linked-list", "tree")})[0]

    assert all(link.url.startswith(BASE) and link.url.endswith("/") for link in links)
    # The same topic leads to a different tag for each side of it.
    assert (graphs.topic, graphs.url) == ("Graphs", BASE + "graph/")
    assert BASE + "depth-first-search/" in [
        link.url for link in leetcode_topics("algorithms", {"algorithms"}, {
            "sliding-window": 9, "binary-search": 9, "sorting": 9, "recursion": 9, "two-pointers": 9,
        })]


@pytest.mark.parametrize("names,expected", [
    ({"Dynamic Programming"}, ("Dynamic Programming", "dynamic-programming")),
    ({"Graphs"}, ("Graphs", "graph")),
    ({"binary_search"}, ("Binary Search", "binary-search")),
    ({"SQL"}, ("Database", "database")),
    ({"Concurrency"}, ("Concurrency", "concurrency")),
    ({"Trees"}, ("Trees", "tree")),
])
def test_a_skill_that_leetcode_covers_links_to_that_topic(names, expected):
    found = leetcode_topics("some_skill", names, {})

    assert [(link.topic, link.url) for link in found] == [(expected[0], f"{BASE}{expected[1]}/")]


@pytest.mark.parametrize("name", [
    "Kubernetes", "System design", "GraphQL", "Message queues", "Full stack", "PostgreSQL", "Python",
])
def test_a_skill_leetcode_does_not_cover_gets_no_link(name):
    assert leetcode_topics(name.lower().replace(" ", "_"), {name}, {"design": 3}) == []


STUDY = {"gaps": [
    {"leetcode": [{"topic": "Sliding Window", "url": BASE + "sliding-window/", "solved": 0},
                  {"topic": "Stack", "url": BASE + "stack/", "solved": 2}]},
    {"leetcode": [{"topic": "Dynamic Programming", "url": BASE + "dynamic-programming/", "solved": None}]},
]}


def linked(*tasks, theme="Practice", study=STUDY) -> list[str]:
    day = DailyPlanItem(day=1, theme=theme, tasks=list(tasks))
    _add_links([day], study)
    return [link.topic for link in day.links]


@pytest.mark.parametrize("task", [
    "Solve two LeetCode Sliding Window problems.",
    "Solve a sliding‑window problem on leetcode.",  # a non-breaking hyphen
])
def test_a_leetcode_day_links_to_the_topics_it_names(task):
    assert linked(task) == ["Sliding Window"]


def test_several_topics_are_linked_once_each():
    assert linked("LeetCode: Stack and Dynamic Programming.", "More Stack practice.") == [
        "Stack", "Dynamic Programming"]


def test_the_theme_can_name_the_topic():
    assert linked("Solve LeetCode problems.", theme="Dynamic programming") == ["Dynamic Programming"]


def test_a_day_that_does_not_speak_of_leetcode_is_not_linked():
    assert linked("Sketch your tech stack.") == []


def test_there_are_no_links_without_a_study_plan():
    assert linked("Solve a LeetCode Stack problem.", study=None) == []
