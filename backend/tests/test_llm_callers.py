"""How features behave when the model fails: they stop asking when asking again
can't help, and say why.
"""
import asyncio

import pytest
from openai import RateLimitError

from app.core import llm
from app.services.career_planner import plan_generation
from app.services.interview import response_generation as interview
from app.services.skill_gap.narrative import InterpretationError, generate_narrative_analysis
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

LIMITED = api_error(RateLimitError, 429)
PLAN = {"question_type": "behavioral", "sections": [{"label": "a", "content": "b"}],
        "follow_up_questions": ["q"], "coaching": [{"focus": "f", "note": "n"}]}


def test_interview_practice_uses_the_configured_model():
    assert interview.INTERVIEW_MODEL == llm.MODEL


def test_interview_planning_stops_when_the_service_is_limited(model):
    model.will(LIMITED)

    with pytest.raises(interview.InterviewGenerationError, match="usage limit"):
        asyncio.run(interview.generate_answer_plan({}, interview.DEFAULT_BLUEPRINT))
    assert len(model.requests) == 1


def test_interview_planning_keeps_trying_after_unreadable_replies(model):
    # Two unreadable replies use up one planning attempt; the next succeeds.
    model.will("nonsense", "nonsense", PLAN)

    plan, _grounding = asyncio.run(interview.generate_answer_plan({}, interview.DEFAULT_BLUEPRINT))

    assert plan.question_type == "behavioral"
    assert len(model.requests) == 3


def test_interview_answer_writing_stops_when_the_service_is_limited(model):
    model.will(LIMITED)

    with pytest.raises(interview.InterviewGenerationError, match="usage limit"):
        asyncio.run(interview.generate_prose_from_plan({}, interview.AnswerPlan()))
    assert len(model.requests) == 1


def test_an_unclassified_question_gets_the_default_blueprint(model):
    model.will(LIMITED)

    assert asyncio.run(interview.classify_blueprint("Why us?")) == interview.DEFAULT_BLUEPRINT


def chunk(days):
    return asyncio.run(plan_generation._generate_chunk({"topic_signals": []}, days, []))


def test_the_planner_stops_asking_when_the_service_is_limited(model):
    model.will(LIMITED)

    plan = chunk([1, 2])

    assert [(item.day, item.source) for item in plan] == [(1, "fallback"), (2, "fallback")]
    assert len(model.requests) == 1


def test_the_planner_asks_again_for_missing_days(model):
    model.will(
        {"daily_plan": [{"day": 1, "theme": "one"}]},
        {"daily_plan": [{"day": 2, "theme": "two"}]},
    )

    assert [(item.theme, item.source) for item in chunk([1, 2])] == [("one", "llm"), ("two", "llm")]


def test_a_bare_string_in_the_summary_is_read_as_a_list(model):
    model.will({"executive_summary": "s", "risks": "one risk", "invented": "x"})

    result = asyncio.run(generate_narrative_analysis({}))

    assert (result.risks, result.strengths) == (["one risk"], [])


def test_a_summary_cut_off_before_the_risks_is_refused(model):
    model.will({"executive_summary": "s"}, {"executive_summary": "s"})

    with pytest.raises(InterpretationError):
        asyncio.run(generate_narrative_analysis({}))
