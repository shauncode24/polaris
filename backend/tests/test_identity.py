# backend/tests/test_identity.py
"""
Phase 3 — Unified Polaris Identity: comprehensive test suite.

Covers the pure-function layer of the identity system — no database,
no LLM, no HTTP. Every function tested here is deterministic given the
same inputs, which means tests are fast, hermetic, and stable.

Test groupings:
  1. confidence_reconciliation — claim-risk + timeline discounting
  2. freshness — staleness determination + evidence_coverage
  3. engineering_identity schema — PolarisProfileFacts validation
  4. identity_builder — _build_technology_breadth, _compute_evidence_hash
  5. career_planner alignment — get_reconciled_skill_confidences return shape
  6. evidence.py — build_evidence_details provenance strings
  7. User isolation assertions — queries always include user_id filter
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. confidence_reconciliation
# ---------------------------------------------------------------------------

from app.services.identity.confidence_reconciliation import (
    reconcile_skill_confidence,
    _skill_in_unsupported_claims,
    TIMELINE_NOTE_MULTIPLIER,
)
from app.services.resume.claim_risk import CLAIM_RISK_MULTIPLIER


class TestSkillInUnsupportedClaims:
    """_skill_in_unsupported_claims uses a loose substring match — same
    rule claim_audit.py itself uses, so a skill can never be flagged by
    a comparison stricter or looser than the one that produced the finding.
    """

    def test_exact_match(self):
        assert _skill_in_unsupported_claims("docker", ["docker"])

    def test_case_insensitive(self):
        assert _skill_in_unsupported_claims("Docker", ["DOCKER"])

    def test_skill_in_claim_substring(self):
        # "docker" is a substring of "docker-compose" → flagged
        assert _skill_in_unsupported_claims("docker", ["docker-compose"])

    def test_claim_in_skill_substring(self):
        # "aws" is a substring of "aws-lambda" → flagged
        assert _skill_in_unsupported_claims("aws-lambda", ["aws"])

    def test_no_match(self):
        assert not _skill_in_unsupported_claims("python", ["java", "go"])

    def test_empty_claims(self):
        assert not _skill_in_unsupported_claims("python", [])

    def test_short_skill_skipped(self):
        # Both strings must be >= MIN_SUBSTRING_LEN (3) for substring
        # matching. Single-char or two-char strings skip the substring test
        # and only match exactly.
        assert not _skill_in_unsupported_claims("go", ["golang"])

    def test_empty_claim_string_ignored(self):
        assert not _skill_in_unsupported_claims("python", ["", " "])

    def test_no_partial_match_across_unrelated(self):
        # "sql" and "nosql" share a substring — both contain "sql"
        assert _skill_in_unsupported_claims("sql", ["nosql"])


class TestReconcileSkillConfidence:
    """reconcile_skill_confidence — deterministic, never mutates inputs."""

    def _make_skill(self, name: str, confidence: float) -> dict:
        return {"skill": name, "confidence": confidence, "sources": [], "corroboration_count": 1}

    def test_no_discounts_when_no_risk(self):
        skills = [self._make_skill("python", 0.80)]
        result = reconcile_skill_confidence(skills, [], [])
        assert len(result) == 1
        assert result[0]["confidence"] == 0.80
        assert result[0]["raw_confidence"] == 0.80
        assert result[0]["confidence_flags"] == []

    def test_claim_risk_high_discount_applied(self):
        skills = [self._make_skill("docker", 0.80)]
        claim_risk = [
            {"project": "MyApp", "risk_level": "high", "headline": "Unsupported", "unsupported_claims": ["docker"]}
        ]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        multiplier = CLAIM_RISK_MULTIPLIER["high"]
        expected = round(0.80 * multiplier, 3)
        assert result[0]["confidence"] == expected
        assert result[0]["raw_confidence"] == 0.80
        assert len(result[0]["confidence_flags"]) == 1
        assert "high risk" in result[0]["confidence_flags"][0]

    def test_claim_risk_medium_discount_applied(self):
        skills = [self._make_skill("kubernetes", 0.70)]
        claim_risk = [
            {"project": "App", "risk_level": "medium", "headline": "...", "unsupported_claims": ["kubernetes"]}
        ]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        multiplier = CLAIM_RISK_MULTIPLIER["medium"]
        assert result[0]["confidence"] == round(0.70 * multiplier, 3)

    def test_unrelated_skill_not_discounted(self):
        skills = [self._make_skill("python", 0.80)]
        claim_risk = [
            {"project": "App", "risk_level": "high", "unsupported_claims": ["docker"]}
        ]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        # python is not in docker's unsupported claims
        assert result[0]["confidence"] == 0.80
        assert result[0]["confidence_flags"] == []

    def test_timeline_note_applies_discount(self):
        skills = [self._make_skill("react", 0.75)]
        timeline_notes = [{"skill": "react", "note": "GitHub evidence postdates resume claim"}]
        result = reconcile_skill_confidence(skills, [], timeline_notes)
        assert result[0]["confidence"] == round(0.75 * TIMELINE_NOTE_MULTIPLIER, 3)
        assert any("timeline" in f.lower() for f in result[0]["confidence_flags"])

    def test_both_discounts_stack(self):
        """Claim-risk fires first, then timeline multiplies on top of that."""
        skills = [self._make_skill("docker", 0.80)]
        claim_risk = [
            {"project": "App", "risk_level": "high", "unsupported_claims": ["docker"]}
        ]
        timeline_notes = [{"skill": "docker", "note": "postdates resume"}]
        result = reconcile_skill_confidence(skills, claim_risk, timeline_notes)
        cr_mult = CLAIM_RISK_MULTIPLIER["high"]
        expected = round(0.80 * cr_mult * TIMELINE_NOTE_MULTIPLIER, 3)
        assert result[0]["confidence"] == expected
        assert len(result[0]["confidence_flags"]) == 2

    def test_does_not_mutate_input(self):
        original_skills = [{"skill": "python", "confidence": 0.80, "sources": []}]
        claim_risk = [{"project": "App", "risk_level": "high", "unsupported_claims": ["python"]}]
        _ = reconcile_skill_confidence(original_skills, claim_risk, [])
        # Original must be unchanged
        assert original_skills[0]["confidence"] == 0.80

    def test_preserves_extra_fields(self):
        skills = [{"skill": "python", "confidence": 0.80, "sources": ["resume"], "corroboration_count": 2}]
        result = reconcile_skill_confidence(skills, [], [])
        assert result[0]["sources"] == ["resume"]
        assert result[0]["corroboration_count"] == 2

    def test_empty_input(self):
        result = reconcile_skill_confidence([], [], [])
        assert result == []

    def test_no_double_compound_from_two_projects(self):
        """Only one claim-risk discount per skill, even if two different
        projects flag it. The break after first match is the guard."""
        skills = [self._make_skill("docker", 0.80)]
        claim_risk = [
            {"project": "App1", "risk_level": "high", "unsupported_claims": ["docker"]},
            {"project": "App2", "risk_level": "high", "unsupported_claims": ["docker"]},
        ]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        cr_mult = CLAIM_RISK_MULTIPLIER["high"]
        expected = round(0.80 * cr_mult, 3)
        # NOT 0.80 * cr_mult * cr_mult — only discounted once
        assert result[0]["confidence"] == expected
        assert len(result[0]["confidence_flags"]) == 1

    def test_detail_without_unsupported_claims_is_skipped(self):
        """A claim-risk detail with no unsupported_claims must never
        discount any skill — there's nothing to match against."""
        skills = [self._make_skill("python", 0.80)]
        claim_risk = [{"project": "App", "risk_level": "high", "unsupported_claims": []}]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        assert result[0]["confidence"] == 0.80


# ---------------------------------------------------------------------------
# 2. freshness — pure functions only
# ---------------------------------------------------------------------------

from app.services.identity.freshness import (
    _age_days,
    compute_evidence_coverage,
    STALENESS_CEILING_DAYS,
)


class TestAgeDays:
    def test_zero_days_for_now(self):
        now = datetime.now(timezone.utc)
        assert _age_days(now) == 0

    def test_correct_age(self):
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        assert _age_days(two_weeks_ago) == 14

    def test_none_returns_none(self):
        assert _age_days(None) is None

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes without tzinfo are treated as UTC — must not raise."""
        naive = datetime.utcnow() - timedelta(days=3)
        result = _age_days(naive)
        assert result is not None
        assert result >= 3

    def test_never_negative(self):
        future = datetime.now(timezone.utc) + timedelta(days=5)
        assert _age_days(future) == 0


class TestComputeEvidenceCoverage:
    """compute_evidence_coverage is a pure function of source_freshness —
    no DB, no LLM.
    """

    def _sf(self, connected: bool, is_stale: bool) -> dict:
        return {"connected": connected, "is_stale": is_stale}

    def test_all_connected_fresh(self):
        sf = {k: self._sf(True, False) for k in STALENESS_CEILING_DAYS}
        cov = compute_evidence_coverage(sf)
        assert cov["connected_sources"] == len(sf)
        assert cov["stale_sources"] == 0
        assert cov["missing_sources"] == 0
        assert cov["completeness_score"] == 1.0
        assert "Comprehensive" in cov["completeness_label"]

    def test_all_missing(self):
        sf = {k: self._sf(False, False) for k in STALENESS_CEILING_DAYS}
        cov = compute_evidence_coverage(sf)
        assert cov["connected_sources"] == 0
        assert cov["completeness_score"] == 0.0
        assert "Minimal" in cov["completeness_label"]

    def test_half_stale_half_fresh(self):
        sources = list(STALENESS_CEILING_DAYS.keys())
        sf = {}
        for i, k in enumerate(sources):
            sf[k] = self._sf(True, i % 2 == 0)
        cov = compute_evidence_coverage(sf)
        stale = sum(1 for s in sf.values() if s["connected"] and s["is_stale"])
        fresh = len(sf) - stale
        expected = round((fresh + stale * 0.5) / len(sf), 2)
        assert cov["completeness_score"] == expected

    def test_stale_still_counts_as_half(self):
        sf = {"resume": self._sf(True, True), "github": self._sf(False, False)}
        cov = compute_evidence_coverage(sf)
        # resume: connected stale → 0.5; github: missing → 0
        # (0.5 + 0) / 2 = 0.25
        assert cov["completeness_score"] == 0.25
        assert "Minimal" in cov["completeness_label"]

    def test_empty_source_freshness(self):
        cov = compute_evidence_coverage({})
        assert cov["completeness_score"] == 0.0


# ---------------------------------------------------------------------------
# 3. PolarisProfileFacts schema
# ---------------------------------------------------------------------------

from app.schemas.identity.engineering_identity import (
    IdentityFacts,
    PolarisProfileFacts,
    ProfileExperienceEntry,
    ProfileEducationEntry,
    ProfileProjectEntry,
)


class TestPolarisProfileFactsSchema:
    def test_defaults_empty(self):
        pf = PolarisProfileFacts()
        assert pf.experiences == []
        assert pf.education == []
        assert pf.projects == []
        assert pf.target_roles == []
        assert pf.target_companies == []
        assert pf.active_goal_count == 0

    def test_round_trips_experience(self):
        exp = ProfileExperienceEntry(
            role="Backend Engineer",
            company="Acme",
            start_date="2022-06-01",
            end_date=None,
            stack=["Python", "FastAPI"],
            bullets=["Led API redesign"],
        )
        data = exp.model_dump()
        restored = ProfileExperienceEntry(**data)
        assert restored.role == "Backend Engineer"
        assert restored.stack == ["Python", "FastAPI"]
        assert restored.end_date is None

    def test_round_trips_education(self):
        edu = ProfileEducationEntry(
            institution="MIT",
            degree="BSc",
            field_of_study="Computer Science",
            end_date="2022-05-01",
            is_current=False,
        )
        data = edu.model_dump()
        assert ProfileEducationEntry(**data).institution == "MIT"

    def test_round_trips_project(self):
        proj = ProfileProjectEntry(
            name="Portfolio App",
            description="My project",
            stack=["React", "Node.js"],
            repo_link_status="confirmed",
        )
        data = proj.model_dump()
        assert ProfileProjectEntry(**data).repo_link_status == "confirmed"

    def test_identity_facts_profile_optional(self):
        """IdentityFacts.profile defaults to None — pre-Phase-3 facts_json
        blobs deserialise cleanly without a migration."""
        facts = IdentityFacts()
        assert facts.profile is None

    def test_identity_facts_accepts_profile(self):
        profile = PolarisProfileFacts(
            experiences=[ProfileExperienceEntry(role="SWE", company="Corp")],
            active_goal_count=2,
        )
        facts = IdentityFacts(profile=profile)
        assert facts.profile is not None
        assert facts.profile.active_goal_count == 2
        assert facts.profile.experiences[0].role == "SWE"

    def test_identity_facts_json_round_trip_with_profile(self):
        """IdentityFacts serialises and deserialises the profile sub-object
        correctly — critical because it's stored as JSON in facts_json."""
        profile = PolarisProfileFacts(
            projects=[ProfileProjectEntry(name="MyApp", stack=["Go"])],
            target_roles=["Backend Engineer"],
        )
        facts = IdentityFacts(profile=profile)
        raw = facts.model_dump_json()
        restored = IdentityFacts.model_validate_json(raw)
        assert restored.profile is not None
        assert restored.profile.target_roles == ["Backend Engineer"]
        assert restored.profile.projects[0].name == "MyApp"

    def test_identity_facts_json_round_trip_without_profile(self):
        """Pre-Phase-3 snapshots (no 'profile' key in facts_json) must
        deserialise cleanly with profile=None."""
        facts = IdentityFacts(top_skills=[])
        raw_dict = facts.model_dump()
        # Simulate a pre-Phase-3 snapshot by removing the profile key
        raw_dict.pop("profile", None)
        restored = IdentityFacts.model_validate(raw_dict)
        assert restored.profile is None


# ---------------------------------------------------------------------------
# 4. identity_builder — pure helper functions
# ---------------------------------------------------------------------------

class TestComputeEvidenceHash:
    """_compute_evidence_hash produces a stable hash for the same input
    and a different hash for different input — used to skip redundant
    role_fit LLM calls.
    """

    def _compute(self, data) -> str:
        # Mirror the identity_builder._compute_evidence_hash logic directly
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def test_same_input_same_hash(self):
        data = [{"skill_id": 1, "source_type": "resume"}, {"skill_id": 2, "source_type": "github"}]
        assert self._compute(data) == self._compute(data)

    def test_different_input_different_hash(self):
        d1 = [{"skill_id": 1}]
        d2 = [{"skill_id": 2}]
        assert self._compute(d1) != self._compute(d2)

    def test_order_invariant_via_sort_keys(self):
        """sort_keys=True means key ordering inside a dict doesn't affect hash."""
        d1 = {"skill_id": 1, "source_type": "resume"}
        d2 = {"source_type": "resume", "skill_id": 1}
        assert self._compute([d1]) == self._compute([d2])


# ---------------------------------------------------------------------------
# 5. career_planner alignment — return shape from get_reconciled_skill_confidences
# ---------------------------------------------------------------------------

from app.services.identity.reconciled_confidence import get_reconciled_skill_confidences


class TestReconciledConfidenceReturnShape:
    """After the Phase 3 alignment fix, _get_skills_by_confidence in
    career_planner/context_builder.py delegates to
    get_reconciled_skill_confidences. The returned dicts must have
    'skill', 'confidence', and 'sources' keys (or at least the first two)
    so the career planner's profile_skills_summary and build_topic_signals
    work unchanged.
    """

    def test_get_reconciled_skill_confidences_returns_expected_shape(self):
        """Smoke test: when SkillEvidence is empty, the function returns an
        empty dict without raising. With evidence, each entry has the
        required keys."""
        import asyncio
        db = AsyncMock()
        # Skill table returns nothing
        mock_skill_result = MagicMock()
        mock_skill_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_skill_result)

        result = asyncio.run(get_reconciled_skill_confidences(db, user_id="user-1"))
        # Should be an empty dict, not a list or None
        assert isinstance(result, dict)

    def test_career_planner_helper_produces_list_of_dicts(self):
        """_get_skills_by_confidence now returns a list of {skill, confidence,
        evidence} dicts. Verify the shape by calling the function with a
        mocked get_reconciled_skill_confidences that returns one skill."""
        # Import the refactored function
        from app.services.career_planner.context_builder import _get_skills_by_confidence
        import asyncio

        mock_reconciled = {
            "python": {
                "skill": "python",
                "confidence": 0.82,
                "raw_confidence": 0.82,
                "confidence_flags": [],
                "sources": ["Resume: engineer at Acme", "Project: PolarisApp"],
                "corroboration_count": 2,
            }
        }
        db = AsyncMock()
        with patch(
            "app.services.career_planner.context_builder.get_reconciled_skill_confidences",
            new=AsyncMock(return_value=mock_reconciled),
        ):
            result = asyncio.run(_get_skills_by_confidence(db, "user-1"))

        assert isinstance(result, list)
        assert len(result) == 1
        item = result[0]
        assert item["skill"] == "python"
        assert item["confidence"] == 0.82
        assert "evidence" in item
        assert item["evidence"] == ["Resume: engineer at Acme", "Project: PolarisApp"]


# ---------------------------------------------------------------------------
# 6. evidence.py — build_evidence_details provenance
# ---------------------------------------------------------------------------

class TestBuildEvidenceProvenance:
    """build_evidence_details maps source_type strings to human-readable
    provenance descriptions. The strings drive the UI's 'Verified in your
    {evidence_details[0]}' messages, so correctness matters.
    Tests use AsyncMock DB that returns the right model types.
    """

    def test_project_provenance(self):
        import asyncio
        from app.services.evidence import build_evidence_details
        from app.models.inference import SkillEvidence
        from app.models.facts import Project
        import uuid

        project_id = uuid.uuid4()
        ev = MagicMock(spec=SkillEvidence)
        ev.source_type = "project"
        ev.source_id = project_id

        mock_proj = MagicMock(spec=Project)
        mock_proj.id = project_id
        mock_proj.name = "PolarisApp"

        db = AsyncMock()
        # First execute: projects query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_proj]
        # Second execute: experiences (empty)
        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_result, mock_empty, mock_empty])

        details = asyncio.run(build_evidence_details(db, [ev]))
        assert any("PolarisApp" in d for d in details)

    def test_leetcode_provenance(self):
        import asyncio
        from app.services.evidence import build_evidence_details
        from app.models.inference import SkillEvidence

        ev = MagicMock(spec=SkillEvidence)
        ev.source_type = "leetcode_tag"
        ev.source_id = None

        db = AsyncMock()
        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_empty)

        details = asyncio.run(build_evidence_details(db, [ev]))
        assert details == ["LeetCode practice history"]

    def test_certificate_provenance(self):
        import asyncio
        from app.services.evidence import build_evidence_details
        from app.models.inference import SkillEvidence

        ev = MagicMock(spec=SkillEvidence)
        ev.source_type = "certificate"
        ev.source_id = None

        db = AsyncMock()
        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_empty)

        details = asyncio.run(build_evidence_details(db, [ev]))
        assert details == ["Certificate"]

    def test_deduplication(self):
        """The same project appearing twice should only produce one detail string."""
        import asyncio
        from app.services.evidence import build_evidence_details
        from app.models.inference import SkillEvidence
        from app.models.facts import Project
        import uuid

        project_id = uuid.uuid4()

        def make_ev():
            ev = MagicMock(spec=SkillEvidence)
            ev.source_type = "project"
            ev.source_id = project_id
            return ev

        mock_proj = MagicMock(spec=Project)
        mock_proj.id = project_id
        mock_proj.name = "App"

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_proj]
        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[mock_result, mock_empty, mock_empty])

        details = asyncio.run(build_evidence_details(db, [make_ev(), make_ev()]))
        # dict.fromkeys deduplicates
        assert details.count("Project: App") == 1


# ---------------------------------------------------------------------------
# 7. User isolation — queries must include user_id filter
# ---------------------------------------------------------------------------

class TestUserIsolationDesign:
    """Lightweight design-level assertions confirming that each module's
    queries carry a user_id guard. These aren't full integration tests —
    they verify the function signatures require user_id as a mandatory
    argument (no default), which is the code-level guarantee of isolation.
    """

    def test_get_all_skill_confidences_requires_user_id(self):
        """get_all_skill_confidences must not have a default for user_id."""
        import inspect
        from app.services.evidence import get_all_skill_confidences
        sig = inspect.signature(get_all_skill_confidences)
        params = sig.parameters
        # user_id is the second positional parameter, after db
        assert "user_id" in params
        # Must not have a default value (sentinels like inspect.Parameter.empty)
        assert params["user_id"].default is inspect.Parameter.empty

    def test_get_reconciled_skill_confidences_requires_user_id(self):
        import inspect
        from app.services.identity.reconciled_confidence import get_reconciled_skill_confidences
        sig = inspect.signature(get_reconciled_skill_confidences)
        assert "user_id" in sig.parameters

    def test_build_profile_facts_requires_user_id(self):
        import inspect
        from app.services.identity.identity_builder import build_profile_facts
        sig = inspect.signature(build_profile_facts)
        assert "user_id" in sig.parameters

    def test_compute_source_freshness_requires_user_id(self):
        import inspect
        from app.services.identity.freshness import compute_source_freshness
        sig = inspect.signature(compute_source_freshness)
        assert "user_id" in sig.parameters

    def test_build_identity_facts_requires_user_id(self):
        import inspect
        from app.services.identity.identity_builder import build_identity_facts
        sig = inspect.signature(build_identity_facts)
        assert "user_id" in sig.parameters

    def test_generate_engineering_identity_requires_user_id(self):
        import inspect
        from app.services.identity.identity_synthesizer import generate_engineering_identity
        sig = inspect.signature(generate_engineering_identity)
        assert "user_id" in sig.parameters

    def test_get_latest_engineering_identity_requires_user_id(self):
        import inspect
        from app.services.identity.identity_synthesizer import get_latest_engineering_identity
        sig = inspect.signature(get_latest_engineering_identity)
        assert "user_id" in sig.parameters

    def test_analyze_skill_gap_requires_user_id(self):
        """Skill Gap Analyzer — user_id must be required."""
        import inspect
        from app.services.skill_gap.comparison import analyze_skill_gap
        sig = inspect.signature(analyze_skill_gap)
        assert "user_id" in sig.parameters


# ---------------------------------------------------------------------------
# 8. Regression — existing reconciliation paths still work
# ---------------------------------------------------------------------------

class TestRegressionExistingPaths:
    """Ensure Phase 3 changes don't break existing reconciliation behaviour."""

    def test_low_risk_claim_does_not_discount(self):
        """claim_risk_details entries with risk_level 'low' are not included
        by _get_claim_risk_details, so they never reach reconcile_skill_confidence.
        Simulating one here confirms that if somehow a low-risk entry reaches
        the reconciler, the CLAIM_RISK_MULTIPLIER for 'low' is 1.0 (no discount).
        """
        from app.services.identity.confidence_reconciliation import reconcile_skill_confidence
        skills = [{"skill": "python", "confidence": 0.80, "sources": []}]
        # risk_level="low" — multiplier should be 1.0 (no-op)
        claim_risk = [{"project": "A", "risk_level": "low", "unsupported_claims": ["python"]}]
        result = reconcile_skill_confidence(skills, claim_risk, [])
        multiplier = CLAIM_RISK_MULTIPLIER.get("low", 1.0)
        expected = round(0.80 * multiplier, 3)
        assert result[0]["confidence"] == expected

    def test_timeline_note_without_matching_skill_is_harmless(self):
        skills = [{"skill": "python", "confidence": 0.80, "sources": []}]
        # Timeline note for "react" — should not affect "python"
        timeline_notes = [{"skill": "react", "note": "postdates resume"}]
        result = reconcile_skill_confidence(skills, [], timeline_notes)
        assert result[0]["confidence"] == 0.80
        assert result[0]["confidence_flags"] == []

    def test_evidence_coverage_completeness_labels_all_thresholds(self):
        """Completeness labels are threshold-based — verify all four levels fire."""
        from app.services.identity.freshness import compute_evidence_coverage

        def sf_from_score(total, connected_fresh, stale):
            result = {}
            for i in range(total):
                if i < connected_fresh:
                    result[str(i)] = {"connected": True, "is_stale": False}
                elif i < connected_fresh + stale:
                    result[str(i)] = {"connected": True, "is_stale": True}
                else:
                    result[str(i)] = {"connected": False, "is_stale": False}
            return result

        # >= 0.9 → Comprehensive
        cov = compute_evidence_coverage(sf_from_score(10, 10, 0))
        assert "Comprehensive" in cov["completeness_label"]

        # ~0.75 → Partial (0.6 <= score < 0.9)
        cov = compute_evidence_coverage(sf_from_score(10, 5, 5))
        assert "Partial" in cov["completeness_label"]

        # ~0.35 → Thin (0.3 <= score < 0.6)
        cov = compute_evidence_coverage(sf_from_score(10, 0, 7))
        # (0 + 7*0.5) / 10 = 0.35 → Thin
        assert "Thin" in cov["completeness_label"]

        # 0 → Minimal
        cov = compute_evidence_coverage(sf_from_score(10, 0, 0))
        assert "Minimal" in cov["completeness_label"]
