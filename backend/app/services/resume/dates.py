"""Reading the dates a resume or LinkedIn profile states: "Jun 2025", "2023",
"Present", "Expected 2027".

Two things are stored. The date column holds the first day of the stated
period, for ordering and comparison. The text column keeps the wording, and is
what gets shown: a stated year must never turn into a month nobody wrote.
Wording that can't be read keeps its text and has no date. No model calls.
"""
import calendar
import re
from datetime import date

MAX_TEXT = 50

_MONTHS = {
    name: number
    for number, names in enumerate([
        ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
        ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
        ("oct", "october"), ("nov", "november"), ("dec", "december"),
    ], start=1)
    for name in names
}
_ONGOING = {"present", "current", "currently", "now", "ongoing", "today", "till date", "to date", "till now"}
_NOT_STATED = {"", "null", "none", "n/a", "na", "-"}
_QUALIFIER = re.compile(
    r"^(?:expected(?: graduation)?|anticipated|graduating|graduation|since|from|spring|summer|fall|autumn|winter)"
    r"\b[\s:]*"
)
# Splits "Jan 2022 - Present" and "2019-2023", but not the ISO month "2022-06".
_RANGE = re.compile(r"\s*[–—]\s*|\s+-\s+|\s+to\s+|(?<=\d{4})\s*-\s*(?=[A-Za-z]|\d{4}|\d{1,2}/)", re.IGNORECASE)
# LinkedIn adds the length of a role: "Jan 2022 - Present · 2 yrs".
_DURATION = re.compile(r"\s*[·•|(].*$")


def _clean(value: str | None) -> str | None:
    text = " ".join((value or "").split())
    return None if text.lower() in _NOT_STATED else text[:MAX_TEXT]


def is_ongoing(text: str | None) -> bool:
    return (text or "").strip().lower() in _ONGOING


def _span(year: int, month: int | None = None, day: int | None = None) -> tuple[date, date] | None:
    if not 1950 <= year <= 2100:
        return None
    try:
        if month is None:
            return date(year, 1, 1), date(year, 12, 31)
        if day is None:
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        return date(year, month, day), date(year, month, day)
    except ValueError:  # no such month or day
        return None


def _period(text: str | None) -> tuple[date, date] | None:
    """The first and last day of the period the text names."""
    s = (text or "").strip().lower()
    while (stripped := _QUALIFIER.sub("", s)) != s:
        s = stripped

    if match := re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", s):
        year, month, day = (int(part) if part else None for part in match.groups())
        return _span(year, month, day)
    if match := re.fullmatch(r"(\d{1,2})[/.-](\d{4})", s):
        return _span(int(match[2]), int(match[1]))
    if match := re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-](\d{4})", s):
        return _span(int(match[1]))  # day and month could be either way round

    words = re.sub(r"[,.]", " ", s)
    words = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", words)
    match = re.fullmatch(r"\s*(?:(\d{1,2})\s+)?([a-z]+)\s*(?:(\d{1,2})\s+)?\s*(?:(\d{4})|['’](\d{2}))\s*", words)
    if match and match[2] in _MONTHS:
        year = int(match[4]) if match[4] else 2000 + int(match[5])
        day = match[1] or match[3]
        return _span(year, _MONTHS[match[2]], int(day) if day else None)
    return None


def last_day(text: str | None) -> date | None:
    period = _period(text)
    return period[1] if period else None


def date_columns(start: str | None, end: str | None = None, *, lone_date_is_end: bool = False) -> dict:
    """The four date columns of an experience or education row, from the dates
    as stated. A whole range may arrive in `start` alone. `lone_date_is_end`
    reads a single date as the finish (a graduation year).
    """
    start, end = _clean(start), _clean(end)
    if start and not end:
        parts = [p for p in _RANGE.split(_DURATION.sub("", start)) if p.strip()]
        if len(parts) > 1:
            start, end = _clean(parts[0]), _clean(parts[-1])
        else:
            start = _clean(parts[0]) if parts else None
            if lone_date_is_end:
                start, end = None, start

    def first(text):
        period = _period(text)
        return period[0] if period else None

    return {
        "start_date": first(start), "end_date": first(end),
        "start_date_text": start, "end_date_text": end,
    }
