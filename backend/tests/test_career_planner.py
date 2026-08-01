from app.services.career_planner.topic_signals import build_topic_signals

def test_build_topic_signals() -> None:
    curriculum_topics = [
        {"domain": "dsa", "topic": "Arrays & Hashing", "suggested_order": 1},
        {"domain": "web", "topic": "API Design (FastAPI/REST)", "suggested_order": 2},
    ]
    skills_by_confidence = [
        {"skill": "fastapi", "confidence": 0.8}
    ]
    leetcode_topic_mastery = [
        {"topic": "Arrays & Hashing", "mastery": "Consistent Practice", "problems": 15}
    ]
    jd_missing_skills = {"fastapi"}
    ats_missing_keywords = {"rest_api"}
    technology_depth = {
        "FastAPI": {"score": 80, "label": "Strong"}
    }

    signals = build_topic_signals(
        curriculum_topics=curriculum_topics,
        skills_by_confidence=skills_by_confidence,
        leetcode_topic_mastery=leetcode_topic_mastery,
        jd_missing_skills=jd_missing_skills,
        ats_missing_keywords=ats_missing_keywords,
        technology_depth=technology_depth,
    )

    assert len(signals) == 2
    
    # Check Arrays & Hashing signal (which uses leetcode mastery)
    dsa_sig = next(s for s in signals if s["topic"] == "Arrays & Hashing")
    assert dsa_sig["coverage"] == "strong"
    assert "LeetCode mastery" in dsa_sig["reasons"][0]

    # Check FastAPI signal (which uses skills_by_confidence, technology_depth and missing flags)
    web_sig = next(s for s in signals if s["topic"] == "API Design (FastAPI/REST)")
    assert web_sig["coverage"] == "strong"  # from skills_by_confidence first priority
    # reasons should include the missing flags from JD and ATS
    reasons = web_sig["reasons"]
    assert any("related skill flagged missing" in r for r in reasons)
    assert any("related keyword flagged missing" in r for r in reasons)
