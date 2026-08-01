import re
from app.services.resume.analysis.shared_signals import (
    EMAIL_PATTERN, PHONE_PATTERN, has_email, has_phone,
)

EXPECTED_SECTIONS = ["experience", "education", "skills", "project"]
MIN_WORD_COUNT = 150
MAX_WORD_COUNT = 1200


def run_ats_checks(raw_text: str) -> list[dict]:
    flags: list[dict] = []
    lowered = raw_text.lower()
    word_count = len(raw_text.split())

    if not has_email(raw_text):
        flags.append({
            "type": "missing_contact_email",
            "detail": "No email address detected in the resume text.",
            "severity": "high",
        })

    if not has_phone(raw_text):
        flags.append({
            "type": "missing_contact_phone",
            "detail": "No phone number detected in the resume text.",
            "severity": "medium",
        })

    for section in EXPECTED_SECTIONS:
        if section not in lowered:
            flags.append({
                "type": "missing_section",
                "detail": f"Couldn't find a '{section.title()}' section header.",
                "severity": "medium",
            })

    if word_count < MIN_WORD_COUNT:
        flags.append({
            "type": "resume_too_short",
            "detail": f"Resume text is only ~{word_count} words — may be too sparse for ATS keyword matching.",
            "severity": "medium",
        })
    elif word_count > MAX_WORD_COUNT:
        flags.append({
            "type": "resume_too_long",
            "detail": f"Resume text is ~{word_count} words — consider trimming to 1-2 pages.",
            "severity": "low",
        })

    return flags