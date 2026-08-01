import re
from datetime import date
from app.models.facts import Experience, Project, Education
from app.services.resume.analysis.shared_signals import (
    has_metric,
    opens_with_strong_verb,
    TECH_KEYWORD_POOL,
    EMAIL_PATTERN, PHONE_PATTERN, LINKEDIN_PATTERN, GITHUB_PATTERN,
    has_email, has_phone, has_linkedin, has_github,
)

_FANCY_BULLET_RE = re.compile(r"[▪▫◦◉●►✓✗✦✧✩✱☛☞▶◆◇★☆]")
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")

TECH_KEYWORDS = TECH_KEYWORD_POOL


def analyze_ats_v2(
    raw_text: str,
    experiences: list[Experience],
    projects: list[Project],
    education: list[Education],
    profile_skills: set[str] | None = None
) -> dict:
    lowered_text = raw_text.lower()
    word_count = len(raw_text.split())

    bullets: list[str] = []
    for exp in experiences:
        if exp.bullets:
            bullets.extend(b.strip() for b in exp.bullets if b.strip())
    for proj in projects:
        if proj.description:
            bullets.extend(line.strip("•-*▪ \t") for line in proj.description.split("\n") if len(line.strip()) > 5)

    # 1. Parsing & ATS Compatibility (25%)
    contact_pts = 0
    if EMAIL_PATTERN.search(raw_text): contact_pts += 10
    if PHONE_PATTERN.search(raw_text): contact_pts += 10
    if LINKEDIN_PATTERN.search(raw_text): contact_pts += 5
    if GITHUB_PATTERN.search(raw_text): contact_pts += 5

    header_pts = 0
    headers = ["experience", "education", "skills", "projects"]
    for h in headers:
        if h in lowered_text:
            header_pts += 6
    header_pts = min(25, header_pts)

    has_education_sec = len(education) > 0 or any(alias in lowered_text for alias in ["education", "academic", "study", "school", "university", "college"])
    has_experience_sec = len(experiences) > 0 or any(alias in lowered_text for alias in ["experience", "work history", "employment", "history"])
    has_projects_sec = len(projects) > 0 or any(alias in lowered_text for alias in ["project", "portfolio"])

    completeness_pts = 0
    if has_experience_sec: completeness_pts += 10
    if has_education_sec: completeness_pts += 5
    if has_projects_sec: completeness_pts += 5

    format_pts = 25
    non_ascii_count = len(_NON_ASCII_RE.findall(raw_text))
    fancy_bullet_count = len(_FANCY_BULLET_RE.findall(raw_text))
    format_pts -= min(15, non_ascii_count)
    format_pts -= min(10, fancy_bullet_count * 2)
    format_pts = max(0, format_pts)

    parsing_score = contact_pts + header_pts + completeness_pts + format_pts

    # 2. Resume Completeness (20%)
    sec_check = 0
    if contact_pts >= 20: sec_check += 10
    if "education" in lowered_text: sec_check += 10
    if "experience" in lowered_text: sec_check += 10
    if "skills" in lowered_text: sec_check += 10
    if "projects" in lowered_text: sec_check += 10

    qty_check = 0
    if has_experience_sec: qty_check += 15
    if has_projects_sec: qty_check += 15
    if has_education_sec: qty_check += 10

    unique_skills = set()
    for exp in experiences:
        if exp.stack: unique_skills.update(s.lower() for s in exp.stack)
    for proj in projects:
        if proj.stack: unique_skills.update(s.lower() for s in proj.stack)
    if profile_skills:
        unique_skills.update(s.lower() for s in profile_skills)
    qty_check += min(10, len(unique_skills) * 2)

    completeness_score = sec_check + qty_check

    # 3. Content Quality (25%) — now uses shared_signals for metric/verb detection
    action_verb_count = 0
    quantified_count = 0
    tech_mention_count = 0
    good_length_count = 0

    total_bullets = len(bullets)
    for b in bullets:
        words = b.split()
        if not words:
            continue
        if opens_with_strong_verb(b):
            action_verb_count += 1
        if has_metric(b):
            quantified_count += 1
        tech_mention_count += sum(1 for kw in TECH_KEYWORDS if f" {kw} " in f" {b.lower()} ")
        if len(words) > 10:
            good_length_count += 1

    action_verb_pts = round((action_verb_count / total_bullets) * 30) if total_bullets > 0 else 0
    quantified_pts = round((quantified_count / total_bullets) * 30) if total_bullets > 0 else 0
    tech_pts = min(20, tech_mention_count * 4)
    length_pts = round((good_length_count / total_bullets) * 10) if total_bullets > 0 else 0

    density_pts = 10
    if word_count < 150:
        density_pts = max(0, 10 - (150 - word_count) // 15)
    elif word_count > 1200:
        density_pts = max(0, 10 - (word_count - 1200) // 100)

    content_quality_score = action_verb_pts + quantified_pts + tech_pts + length_pts + density_pts

    # 4. Resume Structure & Organization (15%)
    struct_pts = 40
    if len(experiences) > 1:
        dates = [exp.start_date for exp in experiences if exp.start_date]
        if dates != sorted(dates, reverse=True):
            struct_pts -= 15

    proj_pts = 20
    if len(projects) > 1:
        p_dates = [p.created_at.date() for p in projects if p.created_at]
        if p_dates != sorted(p_dates, reverse=True):
            proj_pts -= 10

    timeline_pts = 40
    for exp in experiences:
        if exp.start_date and exp.end_date and exp.start_date > exp.end_date:
            timeline_pts -= 20
        for other in experiences:
            if other.id != exp.id and exp.start_date and exp.end_date and other.start_date and other.end_date:
                if exp.start_date < other.end_date and other.start_date < exp.end_date:
                    timeline_pts -= 10
                    break
    timeline_pts = max(0, timeline_pts)

    structure_score = struct_pts + proj_pts + timeline_pts

    # 5. Keyword Coverage (10%)
    matched_tech = sum(1 for kw in TECH_KEYWORDS if kw in lowered_text)
    keyword_score = min(100, matched_tech * 10)

    # 6. Professionalism (5%)
    email_pts = 40 if EMAIL_PATTERN.search(raw_text) else 0
    link_pts = 0
    if GITHUB_PATTERN.search(raw_text): link_pts += 20
    if LINKEDIN_PATTERN.search(raw_text): link_pts += 20

    consistency_pts = 20
    slashed = len(re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", raw_text))
    written = len(re.findall(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}", lowered_text))
    if slashed > 0 and written > 0:
        consistency_pts -= 10

    professionalism_score = email_pts + link_pts + consistency_pts

    overall = (
        parsing_score * 0.25 +
        completeness_score * 0.20 +
        content_quality_score * 0.25 +
        structure_score * 0.15 +
        keyword_score * 0.10 +
        professionalism_score * 0.05
    )

    warnings = []
    if not EMAIL_PATTERN.search(raw_text):
        warnings.append({"type": "missing_email", "severity": "high", "detail": "Missing contact email address."})
    if not PHONE_PATTERN.search(raw_text):
        warnings.append({"type": "missing_phone", "severity": "medium", "detail": "Missing phone number."})
    if not GITHUB_PATTERN.search(raw_text):
        warnings.append({"type": "missing_github", "severity": "low", "detail": "Missing GitHub profile link."})
    if not LINKEDIN_PATTERN.search(raw_text):
        warnings.append({"type": "missing_linkedin", "severity": "low", "detail": "Missing LinkedIn profile link."})
    if not has_experience_sec:
        warnings.append({"type": "missing_experience", "severity": "high", "detail": "At least one experience entry is required."})
    if not has_projects_sec:
        warnings.append({"type": "missing_projects", "severity": "medium", "detail": "No personal or professional projects detected."})
    if not has_education_sec:
        warnings.append({"type": "missing_education", "severity": "medium", "detail": "No educational history detected."})
    if non_ascii_count > 30:
        warnings.append({
            "type": "encoding_issues", "severity": "medium",
            "detail": f"Detected {non_ascii_count} non-ASCII characters — may cause ATS parsing failures on some platforms."
        })
    if fancy_bullet_count > 8:
        warnings.append({
            "type": "fancy_bullets", "severity": "low",
            "detail": f"Found {fancy_bullet_count} fancy Unicode bullets. Some ATS parsers misread these — prefer plain hyphens."
        })

    return {
        "score": round(overall),
        "module_scores": {
            "parsing": round(parsing_score),
            "completeness": round(completeness_score),
            "content_quality": round(content_quality_score),
            "structure": round(structure_score),
            "keywords": round(keyword_score),
            "professionalism": round(professionalism_score),
        },
        "warnings": warnings,
    }