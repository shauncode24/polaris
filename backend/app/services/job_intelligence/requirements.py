"""A flat view of what a job requires, derived from a JobIntelligenceProfile.

Consumers that only need skill lists (resume analysis, skill frequency) use
this instead of reaching into the profile's enriched structures.
"""
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile


def requirements_from_profile(profile: JobIntelligenceProfile) -> dict:
    return {
        "raw_required": [s.raw for s in profile.enriched_required_skills],
        "raw_implicit": [s.raw for s in profile.enriched_implicit_skills],
        "raw_nice_to_have": [s.raw for s in profile.enriched_nice_to_have],
        "architecture_topics": list(profile.architecture_topics),
        "resolved_skills": list(profile.canonical_skills_map.keys()),
    }
