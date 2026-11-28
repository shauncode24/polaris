"""The tailored resume as the pieces of text that appear on it, in order.

The score, the PDF and the Word file are all made from these, so the three hold
the same words in the same order. Only wording that is on the resume is
included: a suggestion appears once accepted.
"""
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.schemas.resume.tailored import ResumeLine, TailoredResumeDocument

_HEADINGS = {
    "summary": "Summary", "experience": "Experience", "projects": "Projects",
    "education": "Education", "skills": "Skills",
}
# Invisible characters that copying text picks up: soft hyphen, zero-width
# space, byte order mark and the emoji variation selectors.
_INVISIBLE = dict.fromkeys(map(ord, "­​﻿︎️"))


@dataclass(frozen=True)
class Block:
    kind: Literal["name", "contact", "heading", "title", "detail", "bullet"]
    text: str
    parts: tuple[str, ...] = ()  # the contact line's separate details


def clean(text: str | None) -> str:
    """One line of ordinary text: accents composed, and nothing a document
    format can't hold.
    """
    composed = unicodedata.normalize("NFC", (text or "").translate(_INVISIBLE))
    spaced = " ".join(composed.split())
    return "".join(c for c in spaced if unicodedata.category(c) not in ("Cc", "Cs") and c not in "￾￿")


def _date_text(written: str | None, day: date | None) -> str:
    return written or (day.strftime("%b %Y") if day else "")


def _dates(entry, ongoing: bool = False) -> str:
    start = _date_text(entry.start_date_text, entry.start_date)
    end = _date_text(entry.end_date_text, entry.end_date) or ("Present" if ongoing else "")
    return " - ".join(filter(None, [start, end]))


def _bullets(lines: list[ResumeLine]) -> list[tuple[str, str]]:
    return [("bullet", line.text) for line in lines]


def _sections(document: TailoredResumeDocument) -> dict[str, list[tuple[str, str | None]]]:
    summary = document.summary
    return {
        "summary": [("detail", summary.text)] if summary else [],
        "experience": [
            piece
            for e in document.experience
            for piece in [("title", f"{e.role}, {e.company}"), ("detail", _dates(e)), *_bullets(e.bullets)]
        ],
        "projects": [
            piece
            for p in document.projects
            for piece in [
                ("title", p.name), ("detail", p.url), ("detail", ", ".join(p.technologies)), *_bullets(p.bullets),
            ]
        ],
        "education": [
            piece
            for e in document.education
            for piece in [
                ("title", e.institution),
                ("detail", ", ".join(filter(None, [e.degree, e.field_of_study]))),
                ("detail", _dates(e, e.is_current)),
                *_bullets(e.bullets),
            ]
        ],
        "skills": [("detail", ", ".join(skill.name for skill in document.skills))],
    }


def resume_blocks(document: TailoredResumeDocument) -> list[Block]:
    """The name, the contact line, then each section that has something in it,
    in the document's order.
    """
    header = document.header
    contact = [header.email, header.phone, header.location, *(link.url for link in header.links)]
    parts = tuple(filter(None, map(clean, contact)))
    blocks = [Block("name", clean(header.full_name)), Block("contact", " | ".join(parts), parts)]
    sections = _sections(document)
    for name in document.section_order:
        pieces = [Block(kind, clean(text)) for kind, text in sections[name]]
        pieces = [piece for piece in pieces if piece.text]
        if pieces:
            blocks += [Block("heading", _HEADINGS[name]), *pieces]
    return blocks


def plain_text(document: TailoredResumeDocument) -> str:
    """The resume as text, in the document's section order."""
    lines = []
    for block in resume_blocks(document):
        if block.kind == "heading":
            lines.append("")
        # A plain hyphen: the ATS checks count other characters against a resume.
        lines.append(f"- {block.text}" if block.kind == "bullet" else block.text)
    return "\n".join(lines)
