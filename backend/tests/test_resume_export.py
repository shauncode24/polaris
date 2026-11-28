"""The tailored resume as a PDF and a Word file, read back with the parsers the
app uses on uploads. No model, no database.
"""
import io
import uuid
from datetime import date

import docx
import pdfplumber
import pytest

from app.schemas.resume.tailored import TailoredResumeDocument
from app.services.resume.docx_parser import extract_text_from_docx
from app.services.resume.export import UnsupportedCharacters, file_name, pdf_file, word_file
from app.services.resume.pdf_parser import extract_text_from_pdf
from app.services.resume.render import plain_text, resume_blocks
from app.services.resume.tailored_score import score_document

KEYWORDS = {"postgresql", "python", "rest api", "kubernetes"}
SYMBOLS = "Cut costs ≥ 40% → ₹2,00,000 saved (±5%) – “zero” downtime…"


def source() -> dict:
    return {"kind": "experience", "id": str(uuid.uuid4())}


def line(text, **fields) -> dict:
    return {"original": text, "sources": [source()], **fields}


def resume(*, name="Zoë Łukasiewicz-Ñúñez", bullets=(SYMBOLS,), roles=1, **extra) -> TailoredResumeDocument:
    return TailoredResumeDocument(**{
        "header": {
            "full_name": name, "email": "zoe@example.com", "phone": "+91 98765 43210", "location": "Kraków",
            "links": [{"label": "GitHub", "url": "https://github.com/zoe"},
                      {"label": "LinkedIn", "url": "https://www.linkedin.com/in/zoe"}],
        },
        "experience": [{
            "role": "Backend Engineer", "company": f"Société Générale {number}", "start_date": date(2022, 3, 1),
            "end_date_text": "Present", "bullets": [line(b) for b in bullets], "sources": [source()],
        } for number in range(roles)],
        "projects": [{
            "name": "Ledger", "url": "https://github.com/zoe/ledger", "technologies": ["Python", "PostgreSQL"],
            "bullets": [line("Built a REST API for double-entry bookkeeping.")], "sources": [source()],
        }],
        "education": [{"institution": "Uniwersytet Jagielloński", "degree": "BSc", "start_date_text": "2018",
                       "end_date_text": "2022", "sources": [source()]}],
        "skills": [{"name": n, "canonical": n.lower(), "sources": [source()]} for n in ("PostgreSQL", "Python")],
        **extra,
    })


def pdf_text(document) -> str:
    return extract_text_from_pdf(io.BytesIO(pdf_file(document)))


def word_text(document) -> str:
    return extract_text_from_docx(io.BytesIO(word_file(document)))


def words(text: str) -> list[str]:
    """The text's words, without the bullet marks, however its lines wrap."""
    return [word for word in text.split() if word != "-"]


READERS = {"pdf": pdf_text, "docx": word_text}


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_the_file_holds_every_word_of_the_resume_in_order(read):
    document = resume()

    assert words(read(document)) == words(plain_text(document))


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_a_long_resume_runs_over_pages_without_losing_anything(read):
    bullets = [f"Delivered milestone {n} of the PostgreSQL migration for the billing and ledger services, "
               "keeping every report available throughout." for n in range(8)]
    document = resume(bullets=bullets, roles=6)

    assert words(read(document)) == words(plain_text(document))


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
@pytest.mark.parametrize("roles", [1, 5])
def test_the_file_scores_the_same_as_the_editor_shows(read, roles):
    document = resume(bullets=("Tuned Postgres queries for the REST API, cutting report time by 40%.",), roles=roles)

    assert score_document(document, KEYWORDS, text=read(document)) == score_document(document, KEYWORDS)


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_only_approved_wording_is_exported(read):
    document = resume()
    document.experience[0].bullets = [
        line("Kept original.", rewrite="Pending suggestion."),
        line("Also kept.", rewrite="Rejected suggestion.", decision="rejected"),
        line("Replaced one.", rewrite="Accepted suggestion.", decision="accepted"),
        line("Replaced two.", edited="My own edit."),
    ]
    document = TailoredResumeDocument.model_validate(document.model_dump())

    text = " ".join(words(read(document)))

    for shown in ("Kept original.", "Also kept.", "Accepted suggestion.", "My own edit."):
        assert shown in text
    for unshown in ("Pending suggestion", "Rejected suggestion", "Replaced"):
        assert unshown not in text


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_sections_follow_the_chosen_order(read):
    order = ["summary", "skills", "education", "projects", "experience"]

    text = read(resume(section_order=order)).splitlines()

    headings = [t for t in text if t in ("Skills", "Education", "Projects", "Experience")]
    assert headings == ["Skills", "Education", "Projects", "Experience"]


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_text_that_looks_like_markup_is_printed_as_written(read):
    tricky = 'Used <b>tags</b> & <img src="/etc/passwd"/> in C++ <3 </para>'

    assert tricky in " ".join(words(read(resume(bullets=(tricky,)))))


@pytest.mark.parametrize("read", READERS.values(), ids=READERS)
def test_stray_characters_from_copied_text_are_cleaned(read):
    messy = "Built\x00 the\x0c re­port​ tool﻿ in Café ✔️"

    assert "Built the report tool in Café ✔" in " ".join(words(read(resume(bullets=(messy,)))))


def test_the_pdf_embeds_the_bundled_font():
    with pdfplumber.open(io.BytesIO(pdf_file(resume()))) as pdf:
        fonts = {char["fontname"].split("+")[-1] for page in pdf.pages for char in page.chars}
        about = pdf.metadata

    assert fonts == {"DejaVuSans", "DejaVuSans-Bold"}
    assert about["Title"] == "Zoë Łukasiewicz-Ñúñez - Resume"
    assert about["Author"] == "Zoë Łukasiewicz-Ñúñez"


def test_the_pdf_is_one_column_inside_its_margins():
    document = resume(bullets=("word " * 80, "x" * 400), roles=3)
    document.header.links[0].url = "https://github.com/" + "z" * 200

    with pdfplumber.open(io.BytesIO(pdf_file(document))) as pdf:
        for page in pdf.pages:
            margin = 18 * 72 / 25.4
            assert all(c["x0"] >= margin - 1 and c["x1"] <= page.width - margin + 1 for c in page.chars)
            # Every line starts at the margin or, for a wrapped or marked bullet, one indent in.
            padding = 6  # ReportLab's, inside the margins
            starts = {round(row["x0"] - margin - padding) for row in page.extract_text_lines()}
            assert starts <= {0, 11}, starts
            assert not page.images and not page.extract_tables()


def test_web_addresses_are_links_in_the_pdf():
    with pdfplumber.open(io.BytesIO(pdf_file(resume()))) as pdf:
        links = {link["uri"] for page in pdf.pages for link in page.hyperlinks}

    assert links == {"https://github.com/zoe", "https://www.linkedin.com/in/zoe", "https://github.com/zoe/ledger"}


def test_only_web_addresses_become_links():
    document = resume()
    document.projects[0].url = "javascript:alert(1)"

    with pdfplumber.open(io.BytesIO(pdf_file(document))) as pdf:
        links = {link["uri"] for page in pdf.pages for link in page.hyperlinks}

    assert not any("javascript" in link for link in links)


def test_the_word_file_is_plain_paragraphs_in_plain_styles():
    word = docx.Document(io.BytesIO(word_file(resume())))

    assert not word.tables and not word.inline_shapes
    assert not any(p.text for s in word.sections for p in [*s.header.paragraphs, *s.footer.paragraphs])
    used = [(p.style.name, p.text) for p in word.paragraphs]
    assert used[0] == ("Title", "Zoë Łukasiewicz-Ñúñez")
    assert ("Heading 1", "Experience") in used and ("List Bullet", SYMBOLS) in used
    assert {p.style.font.name for p in word.paragraphs} == {"Calibri"}
    assert word.core_properties.author == "Zoë Łukasiewicz-Ñúñez"
    assert word.core_properties.created.year >= 2026


@pytest.mark.parametrize(("text", "refused"), [
    ("张伟", "张"), ("अनिल", "अ"), ("Shipped it 🚀", "🚀"), ("שלום", "ש"), ("مرحبا", "م"),
])
def test_text_the_pdf_cannot_show_is_refused_but_the_word_file_takes_it(text, refused):
    document = resume(bullets=(text,))

    with pytest.raises(UnsupportedCharacters, match="Word file") as error:
        pdf_file(document)

    assert refused in error.value.characters
    assert text in word_text(document)


@pytest.mark.parametrize("name", ["张伟", "Ada 🚀"])
def test_an_unshowable_name_is_refused_too(name):
    with pytest.raises(UnsupportedCharacters):
        pdf_file(resume(name=name))


def test_greek_and_cyrillic_are_shown():
    text = "Γειά σου, Привет"

    assert text in pdf_text(resume(bullets=(text,)))


@pytest.mark.parametrize("make", [pdf_file, word_file])
def test_a_resume_with_only_a_name_can_be_exported(make):
    assert make(TailoredResumeDocument(header={"full_name": "Sam Rivera"}))
    assert [b.kind for b in resume_blocks(TailoredResumeDocument(header={"full_name": "Sam"}))] == ["name", "contact"]


def test_the_file_is_named_for_the_person_job_and_version():
    document = resume(name='Zoë "Z" / Smith')

    assert file_name(document, "Globex: R&D", 3, "pdf") == "Zoë Z Smith - Globex R&D - resume v3.pdf"
    assert file_name(document, None, 1, "docx") == "Zoë Z Smith - resume v1.docx"
    assert len(file_name(resume(name="N" * 300), "C", 1, "pdf")) <= 124
