"""Reconciles a skill's headline confidence number against contradicting
signals already present elsewhere in the same IdentityFacts object —
claim_risk_details (unsupported resume claims not backed by GitHub) and
timeline_plausibility_notes (GitHub evidence for a skill postdating a
resume-claimed usage window).

Fixes the "top_skills vs narrative.contradictions" disagreement flagged
as the Critical finding in the Engineering Identity audit: previously a
skill's confidence was computed purely from decayed evidence weight,
with claim-risk and timeline signals living only in separate,
narrative-facing fields. The same object could assert "Docker: 0.81
confidence" in top_skills while simultaneously saying "Docker's GitHub
evidence contradicts your resume claim" in claim_risk_details, with
nothing in the object itself resolving which one a consumer should
believe. This module is that reconciliation step: every top_skill
entry's confidence is now the SAME confidence a consumer reading
top_skills alone would land on, whether or not they also read
claim_risk_details.

Deterministic only — no LLM call. Reuses the existing claim-risk penalty
table from resume/claim_risk.py so this can never disagree with how
Projects/Resume Tailoring already discount claim risk elsewhere in the
codebase.
"""
from app.services.resume.claim_risk import CLAIM_RISK_MULTIPLIER

# Timeline notes are explicitly "advisory, non-judgmental" per
# timeline_plausibility.py's own docstring — they document a gap worth
# being ready to explain, not a disproven claim the way an unsupported
# resume claim is. The discount here is deliberately lighter than
# claim-risk's.
TIMELINE_NOTE_MULTIPLIER = 0.85

MIN_SUBSTRING_LEN = 3  # mirrors claim_audit.py's own matching rule


def _skill_in_unsupported_claims(canonical_skill: str, unsupported_claims: list[str]) -> bool:
    """Same loose substring match claim_audit.py itself uses to decide a
    claim is unsupported in the first place. Reusing that exact rule
    here means a skill can never be flagged in top_skills by a
    comparison stricter or looser than the one that actually produced
    the claim-risk finding — the two can't drift apart.
    """
    skill_lower = canonical_skill.lower()
    for claim in unsupported_claims:
        claim_lower = (claim or "").strip().lower()
        if not claim_lower:
            continue
        if skill_lower == claim_lower or (
            len(skill_lower) >= MIN_SUBSTRING_LEN
            and len(claim_lower) >= MIN_SUBSTRING_LEN
            and (skill_lower in claim_lower or claim_lower in skill_lower)
        ):
            return True
    return False


def reconcile_skill_confidence(
    top_skills: list[dict],
    claim_risk_details: list[dict],
    timeline_plausibility_notes: list[dict],
) -> list[dict]:
    """Returns a NEW list — never mutates the input — with each skill's
    "confidence" replaced by a reconciled number, plus two new fields:

    - "raw_confidence": the original, pre-discount decayed evidence
      score — kept for traceability, same "never silently overwrite a
      real number, always keep the source fact visible" rule the rest
      of this codebase follows (see e.g. resume/evolution.py's
      confidence_at_upload).
    - "confidence_flags": short strings explaining any discount applied
      — empty list if none. This is what lets the synthesis LLM (and
      any future consumer) see WHY a number moved, instead of just a
      smaller number with no explanation.

    claim_risk_details entries are expected to carry "unsupported_claims"
    (see identity_builder._get_claim_risk_details) — a project-level
    finding with no unsupported_claims never discounts anything, since
    there'd be no way to tell which skill it actually implicates.
    """
    timeline_skills = {
        note["skill"].lower() for note in timeline_plausibility_notes if note.get("skill")
    }

    reconciled: list[dict] = []
    for entry in top_skills:
        canonical = entry["skill"]
        raw_confidence = entry["confidence"]
        confidence = raw_confidence
        flags: list[str] = []

        for detail in claim_risk_details:
            unsupported = detail.get("unsupported_claims", [])
            if not unsupported:
                continue
            if _skill_in_unsupported_claims(canonical, unsupported):
                risk_level = detail.get("risk_level", "medium")
                multiplier = CLAIM_RISK_MULTIPLIER.get(risk_level, 1.0)
                confidence = confidence * multiplier
                flags.append(
                    f"Unresolved claim-risk finding on {detail.get('project', 'a project')} "
                    f"({risk_level} risk) — this skill's evidence includes an unsupported resume claim."
                )
                break  # one discount per skill; don't compound across multiple flagged projects

        if canonical.lower() in timeline_skills:
            confidence = confidence * TIMELINE_NOTE_MULTIPLIER
            flags.append(
                "GitHub evidence for this skill postdates a resume-claimed usage window — see timeline notes."
            )

        reconciled.append({
            **entry,
            "confidence": round(confidence, 3),
            "raw_confidence": round(raw_confidence, 3),
            "confidence_flags": flags,
        })

    return reconciled