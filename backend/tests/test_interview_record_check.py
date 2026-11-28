"""Figures and technologies a text states that the record doesn't show. No model, no database."""
import pytest

from app.services.interview.record_check import Record, unrecorded

RECORD = Record(
    texts=[
        "Cut p95 latency from 800ms to 210ms by adding indexes to PostgreSQL.", "Built REST APIs in Python.",
        "Helped 40 students.", "Raised coverage to 85%.", "Served 12,000 requests.", "May 2025", "Docker",
        "Worked with two designers.",
    ],
    skills={"python", "postgres", "docker", "rest_api"}, hidden=set(),
)


def check(text, record=RECORD, **more):
    found = unrecorded(record, text, **more)
    return found.figures, found.technologies


@pytest.mark.parametrize("text", [
    "I cut it from 800 ms to 210 ms with indexes in Postgres.",
    "In May 2025 I helped forty students and two designers.",
    "Coverage reached 85 percent across 12000 requests.",
    "I containerised it with Docker and wrote a REST API in Python.",
    "I checked p99 latency and used HTML5.",
    "One thing at a time, I tested it, debugged the API and studied the algorithms and data structures.",
])
def test_what_the_record_shows_is_not_reported(text):
    figures, technologies = check(text)

    assert figures == []
    assert technologies in ([], ["HTML5"])


@pytest.mark.parametrize("text,figures", [
    ("I helped 400 students.", ["400"]),
    ("I led three teams.", ["three"]),
    ("Coverage reached 40%.", ["40%"]),  # 40 students is not 40%
    ("It took 85 days.", ["85"]),  # 85% is not 85
    ("Latency fell by 1.5 times.", ["1.5"]),
    ("It served 90, then 90 again.", ["90"]),
])
def test_a_figure_the_record_does_not_state_is_reported_as_written(text, figures):
    assert check(text)[0] == figures


@pytest.mark.parametrize("text,technologies", [
    ("I moved it to Kafka and k8s.", ["k8s", "Kafka"]),
    ("I wrote the service in Go and the screens in React.", ["Go", "React"]),
    ("We ran it on Amazon Web Services.", ["Amazon Web Services"]),
    ("I used MongoDB. Then more MongoDB.", ["MongoDB"]),
])
def test_a_technology_the_record_does_not_show_is_reported(text, technologies):
    assert check(text)[1] == technologies


@pytest.mark.parametrize("text", [
    "Go ahead and ask me. React quickly to the rest of the team.",
    "Spring was busy. I express myself well and each node of the plan held.",
])
def test_ordinary_words_are_not_taken_for_technologies(text):
    assert check(text)[1] == []


def test_a_hidden_skill_is_not_shown_by_the_record():
    record = Record(texts=RECORD.texts, skills={"python"}, hidden={"docker"})

    assert check("I used Docker.", record)[1] == ["Docker"]


def test_a_questions_figures_are_allowed_but_not_experience_of_its_tool():
    question = "Design Kafka ingestion for 500 events a second."

    assert check("I ran Kafka at 500 events a second.", given_figures=question) == ([], ["Kafka"])


def test_what_has_already_been_said_can_be_repeated():
    assert check("Your 500 Kafka events.", also_said="I sent 500 events through Kafka.") == ([], [])


def test_a_jobs_own_technologies_are_known_too():
    names = {"ember": {"ember", "ember.js"}}

    assert check("I built it in Ember.", names=names)[1] == ["Ember"]
    assert check("I built it in Ember.")[1] == []


def test_nothing_is_reported_for_an_empty_text():
    assert not unrecorded(RECORD, "")
