# backend/app/services/job_intelligence/seniority.py
"""Stage 6 — seniority classification. Deterministic-first, with three
layers of defense against the "company legacy years read as candidate
experience" failure mode (e.g. "Godrej Group's 125+ year legacy of
trust" being misread as "125 years experience -> Staff"):

  1. `_find_plausible_years_phrase` only trusts a years-phrase if its
     OWN sentence contains no legacy/history language, AND the figure
     is under a plausible ceiling for an individual's experience.
  2. Title/designation ("SDE Trainee", "Engineering Trainee") is
     checked FIRST, before any years phrase, since it's more directly
     authoritative.
  3. `apply_designation_override` runs as a final, unconditional
     backstop AFTER both the deterministic pass and any LLM-assist
     refinement — an entry-level title/designation always wins, no
     matter what upstream logic concluded.
"""
import json
import re

from app.core.llm import chat_completion, MODEL
from app.prompts.seniority_llm import SENIORITY_LLM_SYSTEM_PROMPT
from app.schemas.job_intelligence import SeniorityLevel

MAX_PLAUSIBLE_EXPERIENCE_YEARS = 20

_LEGACY_EXCLUSION_WORDS = [
    "legacy", "founded", "since", "history", "trust", "established",
    "heritage", "anniversary", "years old", "years of excellence",
]

_ENTRY_LEVEL_SIGNALS = [
    "trainee", "intern", "new grad", "graduate trainee", "entry level", "entry-level",
]

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:[-–to]{1,4}\s*(\d+))?\s*\+?\s*years?", re.IGNORECASE)

_TITLE_SIGNALS: dict[str, str] = {
    "intern": "intern",
    "trainee": "junior",
    "new grad": "junior", "junior": "junior", "associate": "junior",
    "mid-level": "mid", "mid level": "mid",
    "staff": "staff", "principal": "staff",
    "lead": "senior", "senior": "senior", "sr.": "senior", "sr ": "senior",
}

_SCOPE_WORDS: dict[str, list[str]] = {
    "staff": ["own the roadmap", "cross-team", "staff-level", "architect the"],
    "senior": ["mentor", "drive technical decisions", "own the design", "lead the"],
}

_VALID_LEVELS = {"intern", "junior", "mid", "senior", "staff", "unspecified"}
_VALID_CONFIDENCE = {"low", "medium", "high"}


def _split_sentences(raw_text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", raw_text)


def _find_plausible_years_phrase(raw_text: str) -> tuple[int, int, str] | None:
    """Scans sentence-by-sentence rather than the whole document at
    once, so a years figure can be checked against its OWN sentence's
    context before being trusted. Two independent guards, either one
    disqualifies the match:
      1. Legacy/history language in that same sentence.
      2. A count over MAX_PLAUSIBLE_EXPERIENCE_YEARS — almost never a
         real per-candidate experience requirement; far more likely a
         company-age claim the sentence-level guard above missed.
    """
    for sentence in _split_sentences(raw_text):
        match = _YEARS_RE.search(sentence)
        if not match:
            continue
        lowered_sentence = sentence.lower()
        if any(w in lowered_sentence for w in _LEGACY_EXCLUSION_WORDS):
            continue
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        if high > MAX_PLAUSIBLE_EXPERIENCE_YEARS:
            continue
        return low, high, sentence.strip()
    return None


def detect_seniority(raw_text: str, role_title: str | None, designation: str | None = None) -> SeniorityLevel:
    lowered = raw_text.lower()
    title_lowered = " ".join(filter(None, [role_title, designation])).lower()
    evidence: list[str] = []
    level: str | None = None

    # Title/designation checked FIRST — it's the most directly
    # authoritative signal a JD gives, and must never be overridden by
    # a years-phrase read later in this same function.
    for signal, lvl in _TITLE_SIGNALS.items():
        if signal in title_lowered:
            level = lvl
            evidence.append(f"Title/designation contains '{signal}'")
            break

    years_info = _find_plausible_years_phrase(raw_text)
    if years_info is not None:
        low, high, sentence = years_info
        evidence.append(f"Years-of-experience phrase found ({low}-{high} years): \"{sentence[:80]}\"")
        if level is None:
            if high <= 1:
                level = "junior"
            elif high <= 4:
                level = "mid"
            elif high <= 8:
                level = "senior"
            else:
                level = "staff"

    if level is None:
        for lvl, words in _SCOPE_WORDS.items():
            if any(w in lowered for w in words):
                level = lvl
                evidence.append(f"Scope language matched a '{lvl}' pattern")
                break

    if level is None:
        return SeniorityLevel(level="unspecified", evidence=[], confidence="low")

    confidence = "high" if len(evidence) >= 2 else "medium"
    return SeniorityLevel(level=level, evidence=evidence, confidence=confidence)


async def refine_seniority_with_llm(raw_text: str, role_title: str | None) -> SeniorityLevel | None:
    """Only called when detect_seniority() found nothing. NEVER raises —
    any failure just means the caller keeps the deterministic
    'unspecified' result.
    """
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": SENIORITY_LLM_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"role_title": role_title, "job_description": raw_text})},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw seniority LLM-assist JSON:\n{content}", flush=True)
        parsed_dict = json.loads(content)

        level = parsed_dict.get("level")
        if level not in _VALID_LEVELS:
            print(f"[TRACING] Seniority LLM-assist returned invalid level '{level}', discarding", flush=True)
            return None
        if level == "unspecified":
            return None

        confidence = parsed_dict.get("confidence")
        if confidence not in _VALID_CONFIDENCE:
            confidence = "medium"

        evidence = parsed_dict.get("evidence")
        if not isinstance(evidence, list):
            evidence = []

        return SeniorityLevel(level=level, evidence=[str(e) for e in evidence][:3], confidence=confidence)
    except Exception as e:
        print(f"[TRACING] Seniority LLM-assist degraded, keeping deterministic result: {e}", flush=True)
        return None


def apply_designation_override(
    seniority: SeniorityLevel, role_title: str | None, designation: str | None
) -> SeniorityLevel:
    """Final, unconditional backstop — runs AFTER both the deterministic
    pass and any LLM-assist refinement. An entry-level title/designation
    ("Engineering Trainee") always wins outright, regardless of what
    upstream logic concluded. This is the hard guarantee against the
    "125-year legacy misread as Staff" failure mode: even if a future
    change reintroduces a years-regex false positive, or the LLM-assist
    call itself misreads the text, this override still catches it.
    """
    text_fields = " ".join(filter(None, [role_title, designation])).lower()
    if any(w in text_fields for w in _ENTRY_LEVEL_SIGNALS) and seniority.level not in ("intern", "junior"):
        return SeniorityLevel(
            level="junior",
            evidence=[f"Title/designation ('{designation or role_title}') indicates an entry-level/trainee role"],
            confidence="high",
        )
    return seniority


async def detect_seniority_with_fallback(
    raw_text: str, role_title: str | None, designation: str | None = None
) -> SeniorityLevel:
    deterministic = detect_seniority(raw_text, role_title, designation)

    if deterministic.level != "unspecified":
        result = deterministic
    else:
        refined = await refine_seniority_with_llm(raw_text, role_title)
        result = refined if refined is not None else deterministic

    return apply_designation_override(result, role_title, designation)