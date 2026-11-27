"""Solved LeetCode problems count toward a job's "data structures" and
"algorithms" requirements, and the job list only shows current scores.

Real endpoints on the real database. Only LLM calls and the identity refresh
are stubbed.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.evidence.state import touch_evidence
from app.services.skill_gap.narrative import InterpretationError
from app.services.skill_gap.prioritization import PrioritizationError
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_job, listing, new_user

# 130 problems over six data-structure and six algorithm topics.
STRONG = {
    "array": 40, "string": 30, "hash-table": 25, "tree": 20, "graph": 10, "stack": 5,
    "dynamic-programming": 35, "greedy": 25, "binary-search": 20, "two-pointers": 15,
    "sorting": 10, "backtracking": 5,
}
# 36 problems over three topics of each.
SOME = {"array": 20, "string": 10, "tree": 6, "greedy": 20, "sorting": 10, "recursion": 6}


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    async def no_narrative(context):
        raise InterpretationError("stubbed")

    async def no_ordering(context):
        raise PrioritizationError("stubbed")

    async def nothing(*args, **kwargs):
        return None

    async def classify(raw_strings):
        # As an LLM might: one tag read as the skill itself, the rest rejected.
        return {raw: ("data_structures", True) if raw == "ordered-set" else (None, False) for raw in raw_strings}

    monkeypatch.setattr("app.api.jobs.generate_narrative_analysis", no_narrative)
    monkeypatch.setattr("app.services.skill_gap.comparison.prioritize_missing_skills", no_ordering)
    monkeypatch.setattr("app.api.jobs.trigger_identity_refresh", nothing)
    monkeypatch.setattr("app.api.sync.trigger_identity_refresh", nothing)
    monkeypatch.setattr("app.services.resume.skill_classifier._classify_via_llm", classify)


def practise(client, user, counts):
    response = client.post("/sync/leetcode/manual", headers=auth(user.id), json={"tag_counts": counts})
    assert response.status_code == 200, response.text[:400]
    return response.json()


def dsa_job(user):
    return add_job(user, "SDE Intern", ["data_structures", "algorithms"])


def match(client, user, job_id):
    response = client.get(f"/jobs/by-intelligence/{job_id}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:400]
    report = response.json()["report"]
    return {e["skill"]: (status, e) for status in ("have", "partial", "missing") for e in report[status]}


def evidence_rows(user, canonical):
    async def go(db):
        result = await db.execute(
            select(SkillEvidence).join(Skill, Skill.id == SkillEvidence.skill_id)
            .where(SkillEvidence.user_id == user.id, Skill.canonical_name == canonical)
        )
        return list(result.scalars().all())
    return run(go)


def age_evidence(user, days):
    async def go(db):
        for row in (await db.execute(select(SkillEvidence).where(SkillEvidence.user_id == user.id))).scalars():
            if row.source_type == "leetcode_tag":
                row.created_at = datetime.now(timezone.utc) - timedelta(days=days)
        await db.commit()
    run(go)


@pytest.mark.parametrize("counts,status", [
    (STRONG, "have"),
    (SOME, "partial"),
    ({"array": 4, "greedy": 4}, "missing"),
], ids=["sustained practice", "some practice", "a few problems"])
def test_practice_decides_how_far_the_requirement_is_met(client, seeded, counts, status):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, counts)

    result = match(client, user, job)

    for skill in ("data_structures", "algorithms"):
        assert result[skill][0] == status, (skill, result[skill])
        assert result[skill][1]["supporting"], "the practice should be shown, even when it isn't enough"


def test_the_evidence_names_the_topics_practised(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, STRONG)

    items = match(client, user, job)["data_structures"][1]["supporting"]

    assert [(i["title"], i["detail"]) for i in items] == [
        ("Data structure practice", "6 topics practised on LeetCode"),
        ("Array", "40 problems solved"),
        ("String", "30 problems solved"),
        ("Hash table", "25 problems solved"),
        ("Tree", "20 problems solved"),
        ("Graph", "10 problems solved"),
    ]
    assert {i["source"] for i in items} == {"leetcode"}


def test_without_practice_the_requirement_is_a_gap(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, {"database": 80})

    assert match(client, user, job)["algorithms"][0] == "missing"
    assert evidence_rows(user, "algorithms") == []


def test_repeated_syncs_keep_one_row_per_skill(client, seeded):
    user = new_user()
    # "ordered-set" is a tag the classifier calls data_structures.
    first = practise(client, user, {**SOME, "ordered-set": 4})
    second = practise(client, user, {**STRONG, "ordered-set": 4})
    third = practise(client, user, {**STRONG, "ordered-set": 4})

    # The sync summary counts each skill once.
    assert [report["skill_evidence"] for report in (first, second, third)] == [
        {"created": 2, "updated": 0, "unchanged": 0},
        {"created": 0, "updated": 2, "unchanged": 0},
        {"created": 0, "updated": 0, "unchanged": 2},
    ]

    assert [len(evidence_rows(user, s)) for s in ("data_structures", "algorithms")] == [1, 1]


def test_a_later_entry_adds_to_what_was_already_recorded(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, SOME)
    # Only two topics this time; the others keep their counts.
    practise(client, user, {"array": 70, "greedy": 60})
    practise(client, user, {"graph": 8, "binary-search": 8})
    practise(client, user, {"stack": 14, "two-pointers": 24})

    result = match(client, user, job)

    assert result["data_structures"][0] == "have"  # array, string, tree, graph, stack; 108 solved
    assert result["algorithms"][0] == "have"


def test_old_practice_fades_until_more_is_solved(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, STRONG)
    age_evidence(user, 800)  # over two years
    practise(client, user, STRONG)  # nothing new solved
    assert match(client, user, job)["algorithms"][0] == "missing"

    practise(client, user, {**STRONG, "greedy": 26})

    assert match(client, user, job)["algorithms"][0] == "have"
    assert match(client, user, job)["data_structures"][0] == "missing"  # nothing new there


def test_the_user_can_hide_practice_based_skills(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, STRONG)

    response = client.put("/profile/skills/algorithms/visibility", headers=auth(user.id), json={"hidden": True})
    assert response.status_code == 200, response.text[:300]

    result = match(client, user, job)
    assert result["algorithms"][0] == "missing"
    assert result["data_structures"][0] == "have"


# --- the job list -----------------------------------------------------------

def test_the_job_list_shows_only_current_scores(client, seeded):
    user = new_user()
    job = dsa_job(user)
    practise(client, user, STRONG)
    assert listing(client, user)[0]["overall_match_percentage"] is None  # not compared yet

    match(client, user, job)
    assert listing(client, user)[0]["overall_match_percentage"] == 75.0

    async def change_evidence(db):
        await touch_evidence(db, user.id)
        await db.commit()
    run(change_evidence)
    assert listing(client, user)[0]["overall_match_percentage"] is None

    match(client, user, job)
    assert listing(client, user)[0]["overall_match_percentage"] == 75.0
