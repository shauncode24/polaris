"""Which rewrites of a resume bullet pass, are flagged, or are removed. No model, no database."""
import uuid

import pytest

from app.schemas.resume.tailored import ResumeLine, SourceRef
from app.services.resume.grounding import check_rewrite, ground_line

BULLET = "Helped the team build 3 internal APIs in Python, cutting report time by 40%."


def passes(original, rewrite) -> bool:
    check = check_rewrite(original, rewrite)
    return not check.flags and not check.new_figures


@pytest.mark.parametrize(("original", "rewrite"), [
    (BULLET, BULLET),
    (BULLET, "helped the team  build 3 internal APIs in Python; cutting report time by 40%"),
    (BULLET, "Helped the team build three internal APIs in Python, cutting report time by 40 percent."),
    ("Tuned Postgres on k8s.", "Tuned PostgreSQL on Kubernetes."),
    ("Wrote JS and ReactJS pages.", "Wrote JavaScript and React.js pages."),
    ("Wrote React pages.", "Wrote React.js pages."),
    ("Deployed to AWS using CI-CD.", "Deployed to Amazon Web Services using CI/CD."),
    ("Designed a REST API.", "Designed a RESTful API."),
    ("Served 1,000 users.", "Served 1000 users."),
    ("Designed, tested and shipped it.", "Designed, tested, shipped it."),
    ("Maintained the lab's C++ and C# tools.", "Maintained the lab’s C++ and C# tools."),
])
def test_the_same_claim_passes(original, rewrite):
    assert passes(original, rewrite)


@pytest.mark.parametrize(("original", "rewrite", "named"), [
    # a technology the bullet doesn't name, even one that counts as the same skill
    ("Set up version control.", "Set up Git.", '"Git"'),
    ("Queried the data warehouse.", "Queried Redshift.", '"Redshift"'),
    ("Containerised the build.", "Dockerized the build.", '"Dockerized"'),
    ("Built services in Python.", "Built services in Python and Kafka.", '"Kafka"'),
    ("Wrote C code.", "Wrote C++ code.", '"C++"'),
    ("Wrote Java code.", "Wrote JavaScript code.", '"JavaScript"'),
    ("Used Node tooling.", "Used Node.js tooling.", '"Node.js"'),
    ("Helped users react to alerts.", "Helped users React.js to alerts.", '"React.js"'),
    # more than the bullet claims
    ("Helped build the API.", "Led and built the API.", '"Led"'),
    ("Built an API.", "Built a scalable API.", '"scalable"'),
    ("Built a REST API.", "Built REST APIs.", '"REST APIs"'),
    ("Was a lead developer.", "Was the lead developer.", '"the"'),
    ("Fixed bugs.", "Fixed all bugs.", '"all"'),
    ("Served users.", "Served thousands of users.", '"thousands"'),
    ("Ranked in the contest.", "Ranked #in the contest.", '"#"'),
    ("Latency changed.", "Latency ↓ changed.", '"↓"'),
])
def test_wording_the_bullet_does_not_have_is_flagged(original, rewrite, named):
    check = check_rewrite(original, rewrite)

    assert check.new_figures == []
    assert any(flag.startswith("Adds") and named in flag for flag in check.flags), check.flags


@pytest.mark.parametrize(("original", "rewrite", "named"), [
    ("Built a small API.", "Built a API.", '"small"'),
    ("Helped build the API.", "Build the API.", '"Helped"'),
    ("Did not own the release.", "Did own the release.", '"not"'),
    ("Tested 2 of the services.", "Tested 2 the services.", '"of"'),
    ("Cut latency by ~40%.", "Cut latency by 40%.", '"~"'),
    ("Grew users 10+.", "Grew users 10.", '"+"'),
    ("Saved $500.", "Saved 500.", '"$"'),
    ("Ran integration tests.", "Ran tests.", '"integration"'),
    ("Built APIs in Python.", "Built APIs.", '"Python"'),
])
def test_dropping_a_word_that_limits_the_claim_is_flagged(original, rewrite, named):
    check = check_rewrite(original, rewrite)

    assert any(flag.startswith("Leaves out") and named in flag for flag in check.flags), check.flags


@pytest.mark.parametrize(("original", "rewrite"), [
    ("Led testing and helped with design.", "Led design and helped with testing."),
    ("Cut time from 40 to 6 seconds.", "Cut time from 6 to 40 seconds."),
    ("Replaced Redis with Kafka.", "Replaced Kafka with Redis."),
])
def test_the_same_words_in_another_order_are_flagged(original, rewrite):
    check = check_rewrite(original, rewrite)

    assert check.new_figures == []
    assert len(check.flags) == 1 and "order" in check.flags[0]


@pytest.mark.parametrize(("original", "rewrite", "figures"), [
    ("Cut report time.", "Cut report time by 40%.", ["40"]),
    ("Cut time by 40%.", "Cut time by 60%.", ["60"]),
    ("Served 40 users.", "Served 400 users.", ["400"]),
    ("Served users.", "Served five users.", ["five"]),
    ("Scored 1,5 points.", "Scored 15 points.", ["15"]),
    ("Improved it by .5%.", "Improved it by 5%.", ["5"]),
    ("Used Python.", "Used Python 3.11.", ["3.11"]),
    ("Handled the load.", "Handled 2x the load.", ["2"]),
    ("Halved the load.", "Cut the load by ½.", ["1", "2"]),
])
def test_a_figure_the_bullet_does_not_state_is_found(original, rewrite, figures):
    assert check_rewrite(original, rewrite).new_figures == figures


def test_each_flag_names_a_word_once_as_written():
    check = check_rewrite("Wrote docs.", "Led Redis work, led Redis docs.")

    assert check.flags == [
        'Adds what your bullet doesn\'t say: "Led", "Redis", "work", "led".',
        'Leaves out: "Wrote".',
    ]


def line(**fields) -> ResumeLine:
    return ResumeLine(sources=[SourceRef(kind="experience", id=uuid.uuid4(), bullet=0)], **fields)


def test_a_rewrite_with_an_invented_figure_is_removed():
    item = line(original="Cut report time.", rewrite="Cut report time by 40%.", decision="accepted")

    ground_line(item)

    assert (item.rewrite, item.decision, item.flags) == (None, "pending", [])
    assert item.text == "Cut report time."


def test_other_changes_stay_with_their_flags_and_the_users_decision():
    item = line(original="Wrote docs.", rewrite="Wrote Redis docs.", decision="accepted", flags=["stale"])

    ground_line(item)

    assert item.rewrite == "Wrote Redis docs."
    assert item.decision == "accepted"  # the user may confirm a flagged rewrite
    assert item.flags == ['Adds what your bullet doesn\'t say: "Redis".']


def test_flags_sent_with_a_line_are_recomputed():
    clean = line(original="Wrote Postgres docs.", rewrite="Wrote PostgreSQL docs.", flags=["made up"])
    bare = line(original="Wrote docs.", flags=["made up"])

    ground_line(clean)
    ground_line(bare)

    assert (clean.flags, bare.flags) == ([], [])


def test_with_nothing_to_fall_back_to_a_rewrite_is_flagged_not_removed():
    summary = line(rewrite="Engineer with 5 years of experience.")

    ground_line(summary)

    assert summary.rewrite and summary.flags


def test_the_users_own_wording_is_not_checked():
    item = line(original="Wrote docs.", edited="Wrote 40 docs.")

    ground_line(item)

    assert (item.text, item.flags) == ("Wrote 40 docs.", [])
