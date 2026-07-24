import re

EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}")
EXPECTED_SECTIONS = ["experience", "education", "skills", "project"]

MIN_WORD_COUNT = 150
MAX_WORD_COUNT = 1200


def run_ats_checks(raw_text: str) -> list[dict]:
    """Deterministic, resume-wide checks — things ATS parsers and
    recruiters both care about, checkable reliably with regex/string
    matching. No LLM call needed at all.
    """
    flags: list[dict] = []
    lowered = raw_text.lower()
    word_count = len(raw_text.split())

    if not EMAIL_PATTERN.search(raw_text):
        flags.append({
            "type": "missing_contact_email",
            "detail": "No email address detected in the resume text.",
            "severity": "high",
        })

    if not PHONE_PATTERN.search(raw_text):
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