"""Module 2 — Parsing / ATS Analyzer.

Checks whether an ATS can reliably parse this resume.
Deterministic regex + heuristics; zero LLM calls.
"""
import re
from app.services.resume.analysis.shared_signals import (
    EMAIL_PATTERN, PHONE_PATTERN, LINKEDIN_PATTERN, GITHUB_PATTERN,
    has_email, has_phone, has_linkedin, has_github,
)

# Fancy Unicode bullets that some ATS systems can't read
_FANCY_BULLET_RE = re.compile(r"[▪▫◦◉●►✓✗✦✧✩✱☛☞▶◆◇★☆]")
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")

MIN_WORDS = 150
MAX_WORDS = 1200
WORDS_PER_PAGE = 475


def analyze_parsing(raw_text: str) -> dict:
    warnings: list[dict] = []
    word_count = len(raw_text.split())

    has_email_flag    = has_email(raw_text)
    has_phone_flag    = has_phone(raw_text)
    has_linkedin_flag = has_linkedin(raw_text)
    has_github_flag   = has_github(raw_text)

    if not has_email_flag:
        warnings.append({
            "type": "missing_email", "severity": "high",
            "detail": "No email address detected. This is required — ATS and recruiters need it.",
        })
    if not has_phone_flag:
        warnings.append({
            "type": "missing_phone", "severity": "medium",
            "detail": "No phone number detected. Recommended for recruiter contact.",
        })
    if not has_linkedin_flag:
        warnings.append({
            "type": "missing_linkedin", "severity": "low",
            "detail": "No LinkedIn URL detected. Most recruiters verify candidates on LinkedIn.",
        })

    # --- Length / page count ---
    page_count = max(1, round(word_count / WORDS_PER_PAGE))
    if word_count < MIN_WORDS:
        warnings.append({
            "type": "too_short", "severity": "medium",
            "detail": f"Resume is only ~{word_count} words — likely too sparse for ATS keyword matching.",
        })
    elif word_count > MAX_WORDS:
        warnings.append({
            "type": "too_long", "severity": "medium",
            "detail": f"Resume is ~{word_count} words (~{page_count} pages). Aim for 1-2 pages.",
        })

    # --- Encoding / formatting issues ---
    non_ascii = len(_NON_ASCII_RE.findall(raw_text))
    if non_ascii > 30:
        warnings.append({
            "type": "encoding_issues", "severity": "medium",
            "detail": f"Detected {non_ascii} non-ASCII characters — may cause ATS parsing failures on some platforms.",
        })

    fancy_bullets = len(_FANCY_BULLET_RE.findall(raw_text))
    if fancy_bullets > 8:
        warnings.append({
            "type": "fancy_bullets", "severity": "low",
            "detail": f"Found {fancy_bullets} fancy Unicode bullets (●, ►, etc.). Some ATS parsers misread these — prefer plain hyphens.",
        })

    # --- Score ---
    high   = sum(1 for w in warnings if w["severity"] == "high")
    medium = sum(1 for w in warnings if w["severity"] == "medium")
    low    = sum(1 for w in warnings if w["severity"] == "low")
    score  = max(0, 100 - high * 20 - medium * 8 - low * 3)

    return {
        "score": round(score),
        "word_count": word_count,
        "page_count_estimate": page_count,
        "has_email":    has_email_flag,
        "has_phone":    has_phone_flag,
        "has_linkedin": has_linkedin_flag,
        "has_github":   has_github_flag,
        "warnings": warnings,
    }
