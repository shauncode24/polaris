# backend/tests/interview/test_grounding_gate.py
"""CI grounding-gate for the Interview Response Agent — implementation plan §Q Phase 3.

Every test here is DETERMINISTIC: no database, no LLM, no network calls.
This means the suite runs fast in CI with zero external dependencies, and
a failure is unambiguous (it is always a code regression, never a flaky
network timeout).

What this covers and why it is the GATE:
  - _scan_prose_for_placeholder_entities — the function that catches
    fabricated project/company names in answer prose. 100% catch-rate on
    known fakes is the pipeline's core reliability promise (implementation
    plan §H). If this regresses, users see hallucinated names.
  - validate_plan / validate_answer — the two grounding passes. These are
    integration points: they call the helpers above. Testing them end-to-end
    with synthetic plan/answer objects verifies that response_generation.py's
    loop actually gates on the right condition.
  - tag_text_deterministic — tier-1 competency tagging. No I/O, pure keyword.
    If a keyword is accidentally removed from COMPETENCY_KEYWORDS, story
    retrieval silently downgrades relevant evidence. CI catches that.
  - GOLDEN_QUESTIONS coverage — every question in the golden set must have an
    expected_blueprint entry, and that entry must be a real blueprint key.
    Verifies the golden set itself stays well-formed as blueprints evolve.

What is NOT tested here and why:
  - The LLM calls (classify_blueprint, generate_answer_plan,
    generate_prose_from_plan) — these require a live model endpoint and are
    covered by the hand-run eval_harness.py golden-set smoke test instead.
  - The database queries in context_builder.py — covered by DB integration
    tests following the test_curation.py pattern.
  - Rubric-axis scoring (the subjective quality axes) — these are LLM-judged
    and tracked as trend via the eval_harness, never a CI hard gate per the
    implementation plan's deliberate design choice.
"""

import pytest

from app.schemas.interview.interview_response import (
    AnswerPlan,
    GroundingReport,
    InterviewLLMOutput,
    PlanEvidenceCitation,
    PlanSection,
)
from app.services.interview.blueprints import BLUEPRINTS
from app.services.interview.competency_tagging import (
    CANONICAL_COMPETENCIES,
    COMPETENCY_KEYWORDS,
    tag_text_deterministic,
)
from app.services.interview.golden_set import GOLDEN_QUESTIONS
from app.services.interview.grounding import (
    _scan_prose_for_placeholder_entities,
    validate_answer,
    validate_plan,
)


# ---------------------------------------------------------------------------
# Helpers — synthetic profile contexts used across tests
# ---------------------------------------------------------------------------

def _make_context(
    projects: list[dict] | None = None,
    experiences: list[dict] | None = None,
    github_repos: list[dict] | None = None,
    leetcode_evidence: dict | None = None,
) -> dict:
    """Minimal synthetic context dict — same shape as what context_builder.py
    produces, so grounding functions see a realistic input."""
    return {
        "profile": {
            "projects": projects or [],
            "experiences": experiences or [],
            "education": [],
            "skills": [],
            "github_repos": github_repos or [],
            "leetcode_evidence": leetcode_evidence,
        },
        "identity": {"claim_risk_details": []},
    }


def _make_plan(
    stories_used: list[str] | None = None,
    cited_evidence: list[dict] | None = None,
    sections: list[dict] | None = None,
    insufficient_context: bool = False,
) -> AnswerPlan:
    return AnswerPlan(
        question_type="behavioral",
        blueprint_used="challenge",
        stories_used=stories_used or [],
        cited_evidence=[
            PlanEvidenceCitation(**c) for c in (cited_evidence or [])
        ],
        sections=[PlanSection(**s) for s in (sections or [])],
        insufficient_context=insufficient_context,
        follow_up_questions=["follow up?"] if not insufficient_context else [],
        coaching=[{"focus": "f", "note": "n"}] if not insufficient_context else [],
    )


def _make_output(
    answer: str = "",
    stories_used: list[str] | None = None,
) -> InterviewLLMOutput:
    return InterviewLLMOutput(
        question_type="behavioral",
        blueprint_used="challenge",
        answer=answer,
        stories_used=stories_used or [],
    )


# ===========================================================================
# 1. _scan_prose_for_placeholder_entities — CI HARD GATE
#    100% catch-rate on injected fakes is the pipeline's core promise.
# ===========================================================================

class TestPlaceholderEntityScanner:
    """These tests constitute the grounding CI hard gate — if ANY of them
    fails, CI must block the merge. A passing hallucination reaches users."""

    @pytest.mark.parametrize("fake_text", [
        "I built Project Alpha in my spare time",
        "I worked at Nova Solutions on a REST API",
        "I contributed to Project Phoenix over six months",
        "I helped innovate solutions for the client",
        "I helped Innovate Solutions build a dashboard",
        "I joined StellarTech as an intern",
        "Our team at Acme Corp shipped the feature",
        "The platform was developed by Tech Innovations",
        "Project Beta was my main contribution",
        "I joined Global Solutions right after college",
    ])
    def test_catches_injected_fake_entity(self, fake_text: str) -> None:
        """Every known fabrication pattern must be caught when no real
        profile evidence matches it."""
        real_names: set[str] = set()  # empty — nothing is real here
        flagged = _scan_prose_for_placeholder_entities(fake_text, real_names)
        assert flagged, (
            f"GROUNDING GATE FAILURE: scanner did NOT flag injected fake in:\n"
            f"  {fake_text!r}\n"
            "This is a CI-blocking regression — the pipeline would let a "
            "hallucinated entity reach the user."
        )

    @pytest.mark.parametrize("real_text,real_names", [
        (
            "I worked at Stripe as a backend engineer",
            {"Stripe"},
        ),
        (
            "My biggest project was called Nova Solutions because my client named it that",
            {"Nova Solutions"},
        ),
        (
            "I built Project Alpha for my capstone",
            {"Project Alpha"},
        ),
    ])
    def test_does_not_flag_real_entities(self, real_text: str, real_names: set[str]) -> None:
        """Entities actually present in the profile must not be flagged —
        false positives trigger unnecessary re-plans."""
        flagged = _scan_prose_for_placeholder_entities(real_text, real_names)
        assert not flagged, (
            f"False positive: scanner flagged a real entity.\n"
            f"  text: {real_text!r}\n"
            f"  real_names: {real_names}\n"
            f"  flagged: {flagged}"
        )

    def test_empty_text_returns_empty(self) -> None:
        assert _scan_prose_for_placeholder_entities("", set()) == []

    def test_empty_text_with_real_names_returns_empty(self) -> None:
        assert _scan_prose_for_placeholder_entities("", {"MyRealProject"}) == []

    def test_deduplicates_repeated_fake(self) -> None:
        text = "I built Project Alpha and then improved Project Alpha."
        flagged = _scan_prose_for_placeholder_entities(text, set())
        assert len(flagged) == 1


# ===========================================================================
# 2. validate_plan — pre-prose grounding gate integration
# ===========================================================================

class TestValidatePlan:

    def test_clean_plan_passes(self) -> None:
        ctx = _make_context(projects=[{"name": "Polaris"}])
        plan = _make_plan(
            stories_used=["Polaris"],
            cited_evidence=[{"source": "Polaris", "fact": "built with FastAPI"}],
            sections=[{"label": "Situation", "content": "Built Polaris for job seekers"}],
        )
        report = validate_plan(plan, ctx)
        assert not report.unverifiable_claims
        assert not report.possible_fabricated_entities
        assert not report.uses_flagged_project

    def test_unreal_story_reference_is_flagged(self) -> None:
        ctx = _make_context(projects=[{"name": "RealProject"}])
        plan = _make_plan(stories_used=["InventedProject"])
        report = validate_plan(plan, ctx)
        assert report.unverifiable_claims, "An invented story_used entry must be flagged"

    def test_unreal_cited_source_is_flagged(self) -> None:
        ctx = _make_context(experiences=[{
            "label": "SWE at Google", "role": "SWE", "company": "Google",
        }])
        plan = _make_plan(
            stories_used=["SWE at Google"],
            cited_evidence=[{"source": "Phantom Corp", "fact": "led a team of 10"}],
        )
        report = validate_plan(plan, ctx)
        assert report.unverifiable_claims

    def test_injected_placeholder_in_section_content_is_flagged(self) -> None:
        ctx = _make_context()
        plan = _make_plan(
            sections=[{"label": "Action", "content": "I worked at Acme Corp to fix this bug"}],
        )
        report = validate_plan(plan, ctx)
        assert report.possible_fabricated_entities

    def test_insufficient_context_plan_returns_a_grounding_report(self) -> None:
        ctx = _make_context()
        plan = _make_plan(insufficient_context=True)
        report = validate_plan(plan, ctx)
        assert isinstance(report, GroundingReport)

    def test_numeric_claim_not_in_evidence_blob_is_flagged(self) -> None:
        ctx = _make_context(projects=[{"name": "MyApp", "description": "A web app"}])
        plan = _make_plan(
            stories_used=["MyApp"],
            cited_evidence=[{"source": "MyApp", "fact": "reduced latency by 50%"}],
            sections=[{"label": "Result", "content": "reduced latency by 50%"}],
        )
        report = validate_plan(plan, ctx)
        assert report.unverifiable_claims, "An invented metric must be flagged"

    def test_numeric_claim_present_in_evidence_blob_passes(self) -> None:
        ctx = _make_context(
            projects=[{"name": "MyApp", "description": "reduced latency by 50%"}],
        )
        plan = _make_plan(
            stories_used=["MyApp"],
            cited_evidence=[{"source": "MyApp", "fact": "reduced latency by 50%"}],
            sections=[{"label": "Result", "content": "reduced latency by 50%"}],
        )
        report = validate_plan(plan, ctx)
        unverifiable_metrics = [c for c in report.unverifiable_claims if "50%" in c]
        assert not unverifiable_metrics

    def test_flagged_project_detected(self) -> None:
        ctx = _make_context(projects=[{"name": "Flagged"}])
        ctx["identity"] = {"claim_risk_details": [{"project": "Flagged", "risk_level": "high"}]}
        plan = _make_plan(stories_used=["Flagged"])
        report = validate_plan(plan, ctx)
        assert report.uses_flagged_project


# ===========================================================================
# 3. validate_answer — post-prose defensive scan integration
# ===========================================================================

class TestValidateAnswer:

    def test_clean_answer_passes(self) -> None:
        ctx = _make_context(experiences=[{
            "label": "SWE at Stripe", "role": "SWE", "company": "Stripe",
        }])
        out = _make_output(
            answer="At Stripe I learned a lot about distributed systems.",
            stories_used=["SWE at Stripe"],
        )
        report = validate_answer(out, ctx)
        assert not report.unverifiable_claims
        assert not report.possible_fabricated_entities

    def test_fabricated_entity_in_prose_is_flagged(self) -> None:
        ctx = _make_context()
        out = _make_output(
            answer="During my time at Acme Corp I shipped the feature.",
            stories_used=[],
        )
        report = validate_answer(out, ctx)
        assert report.possible_fabricated_entities

    def test_invented_metric_in_prose_is_flagged(self) -> None:
        ctx = _make_context(projects=[{"name": "App", "description": "A tool for developers"}])
        out = _make_output(
            answer="I improved performance by 99% which saved the company.",
            stories_used=["App"],
        )
        report = validate_answer(out, ctx)
        assert report.unverifiable_claims


# ===========================================================================
# 4. tag_text_deterministic — tier-1 competency tagging (no I/O)
# ===========================================================================

class TestTagTextDeterministic:

    @pytest.mark.parametrize("competency,keyword_phrase,text", [
        ("leadership", "led ", "I led the backend team for six months"),
        ("leadership", "spearheaded", "I spearheaded the migration to k8s"),
        ("teamwork", "collaborated", "We collaborated with the design team"),
        ("teamwork", "cross-functional", "This was a cross-functional effort"),
        ("ownership", "owned ", "I owned the entire deployment pipeline"),
        ("ownership", "end-to-end", "I was responsible for end-to-end delivery"),
        ("problem_solving", "root cause", "I found the root cause of the timeout bug"),
        ("problem_solving", "debugged", "I debugged the memory leak for a week"),
        ("technical_depth", "architected", "I architected the microservice layer"),
        ("technical_depth", "built from scratch", "We built from scratch a new ingestion system"),
        ("failure_recovery", "mistake", "I made a mistake deploying to production"),
        ("failure_recovery", "rolled back", "I rolled back the broken migration"),
        ("conflict_resolution", "disagreement", "I resolved a disagreement about the API design"),
        ("mentorship", "mentored", "I mentored two junior engineers that semester"),
        ("mentorship", "onboarded", "I onboarded a new hire in my first week"),
    ])
    def test_keyword_detected(self, competency: str, keyword_phrase: str, text: str) -> None:
        tags = tag_text_deterministic(text)
        assert competency in tags, (
            f"Tier-1 keyword {keyword_phrase!r} not detected for competency {competency!r}.\n"
            f"  Text: {text!r}\n"
            f"  Got: {tags}\n"
            "CI REGRESSION: retrieval layer will no longer rank evidence with this "
            f"competency higher — story selection quality silently degrades."
        )

    def test_empty_text_returns_empty_list(self) -> None:
        assert tag_text_deterministic("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert tag_text_deterministic("   ") == []

    def test_plain_tech_stack_list_returns_empty(self) -> None:
        """A purely factual tech-stack bullet with no story language must get zero tags."""
        tags = tag_text_deterministic("Python, FastAPI, PostgreSQL, Docker, Redis")
        assert tags == []

    def test_result_is_sorted(self) -> None:
        """Results must be sorted so caching/hashing is stable."""
        text = "I led the project and also mentored two junior engineers."
        tags = tag_text_deterministic(text)
        assert tags == sorted(tags)

    def test_all_tags_are_canonical(self) -> None:
        text = " ".join(kw for kws in COMPETENCY_KEYWORDS.values() for kw in kws)
        tags = tag_text_deterministic(text)
        for tag in tags:
            assert tag in CANONICAL_COMPETENCIES, (
                f"tag_text_deterministic returned non-canonical tag {tag!r}. "
                "COMPETENCY_KEYWORDS and CANONICAL_COMPETENCIES must stay in sync."
            )

    def test_multiple_competencies_detected_simultaneously(self) -> None:
        text = "I led the team, mentored a junior engineer, and debugged the memory leak."
        tags = tag_text_deterministic(text)
        assert "leadership" in tags
        assert "mentorship" in tags
        assert "problem_solving" in tags


# ===========================================================================
# 5. COMPETENCY_KEYWORDS vocabulary integrity
# ===========================================================================

class TestCompetencyKeywordsIntegrity:
    """Guard the vocabulary contract between COMPETENCY_KEYWORDS and
    CANONICAL_COMPETENCIES. Mismatches silently break the tagging/retrieval contract."""

    def test_every_competency_keyword_key_is_canonical(self) -> None:
        for key in COMPETENCY_KEYWORDS:
            assert key in CANONICAL_COMPETENCIES, (
                f"COMPETENCY_KEYWORDS has entry {key!r} which is NOT in "
                f"CANONICAL_COMPETENCIES — the two dicts have drifted. "
                "tag_text_deterministic would return a non-canonical tag."
            )

    def test_every_canonical_competency_has_keywords(self) -> None:
        for c in CANONICAL_COMPETENCIES:
            assert c in COMPETENCY_KEYWORDS, (
                f"Canonical competency {c!r} has no tier-1 keyword entries. "
                "Evidence tagged with this competency can only be found via "
                "the LLM tier-2 path — tier-1 retrieval will always miss it."
            )

    def test_no_empty_keyword_lists(self) -> None:
        for competency, keywords in COMPETENCY_KEYWORDS.items():
            assert keywords, f"COMPETENCY_KEYWORDS[{competency!r}] is an empty list"


# ===========================================================================
# 6. Golden set well-formedness — CI structural gate
# ===========================================================================

class TestGoldenSetWellFormedness:
    """The golden set is the regression harness's input data. If it's
    structurally broken, the harness produces meaningless results."""

    def test_all_expected_blueprints_are_real_keys(self) -> None:
        for entry in GOLDEN_QUESTIONS:
            bp = entry.get("expected_blueprint")
            if bp is not None:
                assert bp in BLUEPRINTS, (
                    f"Golden-set entry {entry['id']!r} expects blueprint {bp!r} "
                    f"which does not exist in BLUEPRINTS. Either add the blueprint "
                    f"or fix the golden set expectation."
                )

    def test_all_entries_have_required_fields(self) -> None:
        for entry in GOLDEN_QUESTIONS:
            assert "id" in entry, f"Golden-set entry missing 'id': {entry}"
            assert "question" in entry, (
                f"Golden-set entry {entry.get('id')!r} missing 'question'"
            )
            assert "expected_blueprint" in entry, (
                f"Golden-set entry {entry.get('id')!r} missing 'expected_blueprint' — "
                "classification accuracy is unmeasurable without it."
            )

    def test_no_duplicate_ids(self) -> None:
        ids = [e["id"] for e in GOLDEN_QUESTIONS]
        assert len(ids) == len(set(ids)), (
            f"Duplicate IDs in GOLDEN_QUESTIONS: {[i for i in ids if ids.count(i) > 1]}"
        )

    def test_all_question_strings_are_non_empty(self) -> None:
        for entry in GOLDEN_QUESTIONS:
            assert entry["question"].strip(), (
                f"Golden-set entry {entry['id']!r} has an empty question string."
            )

    def test_continuity_followup_references_valid_setup_id(self) -> None:
        setup_ids = {e["id"] for e in GOLDEN_QUESTIONS if e.get("continuity_setup")}
        for entry in GOLDEN_QUESTIONS:
            ref = entry.get("continuity_followup_to")
            if ref is not None:
                assert ref in setup_ids, (
                    f"Golden-set entry {entry['id']!r} references "
                    f"'continuity_followup_to': {ref!r} which has no matching "
                    f"'continuity_setup': True entry."
                )


# ===========================================================================
# 7. BLUEPRINTS library integrity
# ===========================================================================

class TestBlueprintsIntegrity:
    """Guard the blueprint library's structural contract. A malformed blueprint
    breaks classification and plan-generation for that whole question type."""

    def test_all_blueprints_have_objective(self) -> None:
        for key, bp in BLUEPRINTS.items():
            assert bp.get("objective"), (
                f"Blueprint {key!r} is missing a non-empty 'objective'."
            )

    def test_all_blueprints_have_sections(self) -> None:
        for key, bp in BLUEPRINTS.items():
            assert isinstance(bp.get("sections"), list) and bp["sections"], (
                f"Blueprint {key!r} has no sections list or an empty one."
            )

    def test_all_blueprints_have_notes(self) -> None:
        for key, bp in BLUEPRINTS.items():
            assert "notes" in bp, f"Blueprint {key!r} is missing 'notes' key"
            assert isinstance(bp["notes"], list), (
                f"Blueprint {key!r} 'notes' is not a list"
            )

    def test_ownership_and_internship_blueprints_exist(self) -> None:
        """These two were the explicit Phase-0 B gap — their absence caused
        real questions to silently fall back to behavioral_default."""
        assert "ownership" in BLUEPRINTS, (
            "Blueprint 'ownership' is missing — ownership questions get generic treatment."
        )
        assert "internship" in BLUEPRINTS, (
            "Blueprint 'internship' is missing — internship questions get generic treatment."
        )

    def test_generic_fallback_blueprints_exist(self) -> None:
        for fallback in ("behavioral_default", "technical_default", "motivation_default"):
            assert fallback in BLUEPRINTS, (
                f"Generic fallback blueprint {fallback!r} is missing — "
                "classification failures have no safe landing."
            )
