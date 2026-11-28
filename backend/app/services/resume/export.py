"""The tailored resume as a PDF or a Word file to send.

Both have one column of ordinary text with no tables, text boxes, images or
page headers, which screening software reads reliably.

The PDF embeds the bundled DejaVu fonts. They cover Latin, Greek and Cyrillic
letters and common symbols; anything else (Chinese or Devanagari, emoji, or
right-to-left scripts, which would print backwards) is refused rather than
printed wrongly. The Word file takes any text, as the reader's fonts draw it.
"""
import io
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import docx
from docx.shared import Mm, Pt, RGBColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

from app.schemas.resume.tailored import TailoredResumeDocument
from app.services.resume.render import Block, clean, resume_blocks

_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_REGULAR, _BOLD = "DejaVuSans", "DejaVuSans-Bold"
_MARGIN_MM = 18
_BULLET_INDENT = 11  # points
_BOLD_KINDS = ("name", "heading", "title")


class UnsupportedCharacters(ValueError):
    """The PDF fonts can't show some of the text. The message is for the user."""

    def __init__(self, characters: list[str]):
        self.characters = characters
        super().__init__(
            f"The PDF can't show these characters: {' '.join(characters[:10])}. "
            "Edit the lines that use them, or download the Word file instead."
        )


@lru_cache(maxsize=1)
def _fonts() -> dict:
    fonts = {}
    for name in (_REGULAR, _BOLD):
        fonts[name] = TTFont(name, str(_FONT_DIR / f"{name}.ttf"))
        pdfmetrics.registerFont(fonts[name])
    return fonts


def _check_characters(blocks: list[Block]) -> None:
    fonts = _fonts()
    refused: dict[str, None] = {}
    for block in blocks:
        glyphs = fonts[_BOLD if block.kind in _BOLD_KINDS else _REGULAR].face.charToGlyph
        for character in block.text:
            right_to_left = unicodedata.bidirectional(character) in ("R", "AL", "AN")
            if not character.isspace() and (right_to_left or ord(character) not in glyphs):
                refused[character] = None
    if refused:
        raise UnsupportedCharacters(list(refused))


def _style(name: str, size: float, *, bold: bool = False, **options) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=_BOLD if bold else _REGULAR, fontSize=size, leading=size * 1.35, **options,
    )


def _pdf_styles() -> dict[str, ParagraphStyle]:
    return {
        "name": _style("name", 17, bold=True, spaceAfter=2),
        "contact": _style("contact", 9),
        "heading": _style("heading", 11.5, bold=True, spaceBefore=11, spaceAfter=2, keepWithNext=1),
        "title": _style("title", 10, bold=True, spaceBefore=4, keepWithNext=1),
        "detail": _style("detail", 9.5),
        "bullet": _style("bullet", 9.5, leftIndent=_BULLET_INDENT, bulletFontName=_REGULAR, bulletFontSize=9.5),
    }


def _markup(text: str) -> str:
    """`text` for a ReportLab paragraph, which reads markup: escaped, and a web
    address made clickable.
    """
    if text.lower().startswith(("http://", "https://")) and " " not in text:
        return f"<a href={quoteattr(text)}>{escape(text)}</a>"
    return escape(text)


def pdf_file(document: TailoredResumeDocument) -> bytes:
    """Raises `UnsupportedCharacters`."""
    blocks = resume_blocks(document)
    _check_characters(blocks)
    styles = _pdf_styles()

    story = []
    for block in blocks:
        if not block.text:
            continue
        if block.kind == "contact":
            text = " | ".join(_markup(part) for part in block.parts)
        else:
            text = _markup(block.text)
        story.append(Paragraph(text, styles[block.kind], bulletText="-" if block.kind == "bullet" else None))

    output = io.BytesIO()
    name = blocks[0].text
    SimpleDocTemplate(
        output, pagesize=A4, title=f"{name} - Resume", author=name, subject="Resume", creator="Polaris",
        leftMargin=_MARGIN_MM * mm, rightMargin=_MARGIN_MM * mm,
        topMargin=_MARGIN_MM * mm, bottomMargin=_MARGIN_MM * mm,
    ).build(story)
    return output.getvalue()


def _plain_word_style(style, size: float, *, bold: bool) -> None:
    """Black Calibri at this size, replacing the template's themed look."""
    style.font.name = "Calibri"
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = False
    style.font.color.rgb = RGBColor(0, 0, 0)
    # A theme font named on the style would win over the font just set.
    fonts = style.element.rPr.rFonts
    for attribute in [a for a in fonts.attrib if a.lower().endswith("theme")]:
        del fonts.attrib[attribute]


def word_file(document: TailoredResumeDocument) -> bytes:
    blocks = resume_blocks(document)
    word = docx.Document()

    page = word.sections[0]
    page.page_width, page.page_height = Mm(210), Mm(297)
    page.left_margin = page.right_margin = page.top_margin = page.bottom_margin = Mm(_MARGIN_MM)

    # kind of block -> Word style, size, bold, space above
    looks = {
        "name": ("Title", 18, True, 0),
        "contact": ("Normal", 10, False, 0),
        "heading": ("Heading 1", 12, True, 10),
        "title": ("Heading 2", 10.5, True, 4),
        "detail": ("Normal", 10, False, 0),
        "bullet": ("List Bullet", 10, False, 0),
    }
    for style_name, size, bold, above in looks.values():
        style = word.styles[style_name]
        _plain_word_style(style, size, bold=bold)
        style.paragraph_format.space_before = Pt(above)
        style.paragraph_format.space_after = Pt(0)
    # The template underlines titles with a coloured rule.
    properties = word.styles["Title"].element.pPr
    for border in properties.findall(docx.oxml.ns.qn("w:pBdr")):
        properties.remove(border)

    for block in blocks:
        if block.text:
            word.add_paragraph(block.text, style=looks[block.kind][0])

    name, now = blocks[0].text, datetime.now(timezone.utc)
    about = word.core_properties
    about.author = about.last_modified_by = name[:255]
    about.title = f"{name} - Resume"[:255]
    about.subject, about.comments = "Resume", ""
    about.created = about.modified = now

    output = io.BytesIO()
    word.save(output)
    return output.getvalue()


def file_name(document: TailoredResumeDocument, job_name: str | None, version: int, extension: str) -> str:
    parts = [clean(document.header.full_name), clean(job_name), f"resume v{version}"]
    stem = " - ".join(filter(None, parts))
    stem = "".join(" " if c in '\\/:*?"<>|' else c for c in stem)
    return f"{' '.join(stem.split())[:120]}.{extension}"
