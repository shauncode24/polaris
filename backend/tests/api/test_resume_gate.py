"""The truthfulness gate for the tailored resume (implementation plan, after step
37): across ten people and jobs, nothing on a resume says what the person's
record doesn't unless it is flagged, and a resume still comes out when the model
fails.

`unsupported` reads the database itself and compares every fact on a resume with
it. It deliberately shares no code with the app's own checks. The stand-in model
tries a different way of overstating on each bullet.

Real database; stand-in model.
"""
import io
import itertools
import json
import re

import httpx
import pytest
from openai import APIConnectionError
from sqlalchemy import select, update

from app.core import llm
from app.models.facts import Education, Experience, Project, User
from app.models.github_analysis import GithubProjectAnalysis
from app.models.linkedin import LinkedInProfile
from app.models.structure import Skill
from app.schemas.resume.tailored import ExperienceEntry, SkillEntry, TailoredResumeDocument
from app.services.resume.docx_parser import extract_text_from_docx
from app.services.resume.pdf_parser import extract_text_from_pdf
from tests.api.resume_gate_profiles import PROFILES, create
from tests.api.test_evidence import auth, run
from tests.api.test_resume_rewriting import add_job
from tests.llm_stub import reply

# --- The checker -------------------------------------------------------------

# The spellings of one name that these profiles use.
_SAME = {"postgres": "postgresql", "react": "react.js", "ml": "machine learning", "mongo": "mongodb"}


def _own_words(spelling: str) -> str:
    """Matches the spelling as its own words: not "react" within "react.js"."""
    return rf"(?<![a-z0-9]){re.escape(spelling)}(?![a-z0-9]|\.[a-z])"


def _spelled_one_way(text: str) -> str:
    plain = " ".join(text.lower().replace("’", "'").split())
    for spelling, name in _SAME.items():
        plain = re.sub(_own_words(spelling), name, plain)
    return plain


def _says(text: str, name: str) -> bool:
    """Whether `text` has this name, in one of its spellings, as its own words."""
    return re.search(_own_words(_spelled_one_way(name)), _spelled_one_way(text)) is not None


def _claims(text: str) -> list[str]:
    """What a line claims: its words, without punctuation, "a", "an" and "and"."""
    words = re.findall(r"[a-z0-9%+#$.]*[a-z0-9%+#]", _spelled_one_way(text))
    return [w for w in words if w not in ("a", "an", "and")]


def _record(user_id) -> dict:
    """The user's visible evidence, read straight from the tables."""
    async def go(db):
        async def rows(model):
            found = (await db.scalars(select(model).where(model.user_id == user_id))).all()
            return {r.id: r for r in found if not getattr(r, "is_hidden", False)}
        return {
            "user": await db.get(User, user_id),
            "experience": await rows(Experience), "project": await rows(Project),
            "education": await rows(Education), "github_repo": await rows(GithubProjectAnalysis),
            "linkedin_profile": await rows(LinkedInProfile),
        }
    return run(go)


def _bullet(record, ref) -> str | None:
    row = record.get(ref.kind, {}).get(ref.id)
    if row is None or ref.bullet is None:
        return None
    texts = {"experience": lambda: row.bullets, "education": lambda: row.details,
             "project": lambda: (row.description or "").split("\n")}[ref.kind]() or []
    return texts[ref.bullet].strip() if ref.bullet < len(texts) else None


def _skill_texts(record, ref) -> list[str]:
    """Everything the cited source says, as far as naming a skill goes."""
    row = record.get(ref.kind, {}).get(ref.id)
    if row is None:
        return []
    if ref.kind == "experience":
        return [*(row.stack or []), *(row.bullets or [])]
    if ref.kind == "project":
        repo = next((r for r in record["github_repo"].values() if r.repo_name == row.github_repo_name), None)
        return [*(row.stack or []), row.description or "", *((repo.technologies or []) if repo else [])]
    if ref.kind == "github_repo":
        return list(row.technologies or [])
    if ref.kind == "linkedin_profile":
        return list(row.parsed_json.get("skills", []))
    return []


def unsupported(user_id, document: TailoredResumeDocument) -> list[str]:
    """Every statement on the resume, or suggested for it without a warning,
    that the user's record doesn't bear out.
    """
    record, found = _record(user_id), []
    user = record["user"]

    def wrong(what: str, condition: bool):
        if not condition:
            found.append(what)

    header = document.header
    wrong("name", header.full_name == f"{user.first_name} {user.last_name}")
    wrong("email", header.email == user.email)
    wrong("phone", header.phone == user.phone)
    wrong("location", header.location is None)
    allowed_links = {f"https://github.com/{user.github_username}", user.linkedin_url}
    wrong("links", {link.url for link in header.links} <= allowed_links)
    wrong("summary", document.summary is None)

    def row_of(entry, kind):
        row = next((record[kind].get(s.id) for s in entry.sources if s.kind == kind), None)
        wrong(f"{kind} entry cites no visible {kind}", row is not None)
        return row

    def dates(entry, row):
        for field in ("start_date", "end_date", "start_date_text", "end_date_text"):
            wrong(f"{field} of {row.id}", getattr(entry, field) == getattr(row, field))

    for entry in document.experience:
        if (row := row_of(entry, "experience")) is not None:
            wrong(f"role {entry.role}", (entry.role, entry.company) == (row.role.strip(), row.company.strip()))
            dates(entry, row)
    for entry in document.projects:
        if (row := row_of(entry, "project")) is not None:
            repo = next((r for r in record["github_repo"].values() if r.repo_name == row.github_repo_name), None)
            wrong(f"project {entry.name}", entry.name == row.name.strip())
            wrong(f"url {entry.url}", entry.url in (None, row.repo_url, repo.html_url if repo else None))
            listed = {t.strip() for t in [*(row.stack or []), *((repo.technologies or []) if repo else [])]}
            wrong(f"technologies {entry.technologies}", set(entry.technologies) <= listed)
    for entry in document.education:
        if (row := row_of(entry, "education")) is not None:
            wrong(f"education {entry.institution}", (entry.institution, entry.degree, entry.field_of_study)
                  == (row.institution.strip(), row.degree, row.field_of_study))
            dates(entry, row)
            wrong("is_current", entry.is_current == bool(row.is_current))

    for skill in document.skills:
        practised = any(s.kind == "leetcode_tag" for s in skill.sources) and \
            skill.name.lower() == skill.canonical.replace("_", " ")
        stated = any(_says(text, skill.name) for s in skill.sources for text in _skill_texts(record, s))
        wrong(f"skill {skill.name!r}", practised or stated)

    for line in document.lines():
        quoted = {_bullet(record, s) for s in line.sources}
        wrong(f"original {line.original!r}", line.original in quoted)
        wrong(f"edit {line.edited!r}", line.edited is None)
        if line.rewrite and not line.flags:
            wrong(f"unflagged rewrite {line.rewrite!r}", _claims(line.rewrite) == _claims(line.original or ""))
    return found


# --- The stand-in model --------------------------------------------------------

def _overstate(way: str, bullet: str, terms: list[dict], job: list[tuple[str, str]]) -> str:
    stem = bullet.rstrip(".")
    if way == "adds a technology the job wants":
        absent = next((raw for raw, _ in job if raw.lower() not in bullet.lower()), "Kubernetes")
        return f"{stem} using {absent}."
    if way == "adds a figure":
        return f"{stem}, improving performance by 75%."
    if way == "claims leadership":
        return f"Led the work: {bullet[0].lower()}{bullet[1:]}"
    if way == "drops what limits the claim":
        return re.sub(r"\b(Helped|Assisted with|Contributed to|small|some|demo|prototype)\b ?", "", bullet)
    if way == "uses the job's word for the user's":
        for term in terms:
            bullet = bullet.replace(term["in_bullet"], term["term"])
        return bullet
    if way == "reorders the words":
        words = stem.split()
        return " ".join([words[-1], *words[:-1]]) + "."
    if way == "invents an achievement":
        return "Architected distributed systems serving millions of users."
    if way == "makes one thing many":
        return re.sub(r"\ba\b", "several", bullet) if re.search(r"\ba\b", bullet) else f"{stem} across all teams."
    assert way == "returns it unchanged"
    return bullet


WAYS = [
    "uses the job's word for the user's", "adds a technology the job wants", "adds a figure",
    "claims leadership", "drops what limits the claim", "reorders the words", "invents an achievement",
    "makes one thing many", "returns it unchanged",
]


class DishonestModel:
    """Tries each way in turn, except that it is honest about "Postgres", whose
    other spelling may be suggested without a warning.
    """

    def __init__(self):
        self.turn = itertools.count()
        self.used: set[str] = set()
        self.job: list[tuple[str, str]] = []

    async def __call__(self, **request):
        sent = json.loads(request["messages"][1]["content"])
        honest = "Postgres " in sent["bullet"]
        way = WAYS[0] if honest else WAYS[next(self.turn) % len(WAYS)]
        self.used.add(way)
        return reply({"rewrite": _overstate(way, sent["bullet"], sent["job_terms"], self.job)})


async def unreachable(**_request):
    raise APIConnectionError(request=httpx.Request("POST", "http://llm.invalid"))


async def gibberish(**_request):
    return reply("not what was asked for")


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


@pytest.fixture(autouse=True)
def other_peoples_skill_names(seeded):
    """The table of skill names is shared by everyone, so it holds whatever
    spelling someone else's record used first. Here every name in it is one that
    none of these people wrote.
    """
    canonicals = {c for p in PROFILES for c in [canonical for _, canonical in [*p.job, *p.nice]]}
    canonicals |= {c for p in PROFILES for item in [*p.roles, *p.projects] for c in item.skills}
    canonicals |= {c for p in PROFILES for item in p.projects for c in item.repo_skills}
    before: dict = {}

    async def rename(db):
        for canonical in canonicals:
            skill = await db.scalar(select(Skill).where(Skill.canonical_name == canonical))
            if skill is None:
                skill = Skill(canonical_name=canonical, name=canonical)
                db.add(skill)
                await db.flush()
            before[skill.id] = skill.name
            skill.name = f"Someone else's {canonical}"
        await db.commit()

    async def restore(db):
        for skill_id, name in before.items():
            await db.execute(update(Skill).where(Skill.id == skill_id).values(name=name))
        await db.commit()

    run(rename)
    yield
    run(restore)


def generate(client, user, job) -> TailoredResumeDocument:
    response = client.post(f"/tailored-resumes/{job}", headers=auth(user.id))
    assert response.status_code == 200, response.text[:300]
    return TailoredResumeDocument.model_validate(response.json()["resume"]["document"])


def exported(client, user, job) -> list[str]:
    """The words of both downloads."""
    texts = []
    for file_format, read in (("pdf", extract_text_from_pdf), ("docx", extract_text_from_docx)):
        response = client.get(
            f"/tailored-resumes/{job}/versions/1/export?format={file_format}", headers=auth(user.id))
        assert response.status_code == 200, response.text[:300]
        texts.append(" ".join(read(io.BytesIO(response.content)).split()))
    return texts


# --- The gate ------------------------------------------------------------------

def test_there_are_ten_different_pairs():
    assert len({p.key for p in PROFILES}) == len(PROFILES) >= 10


def test_no_resume_makes_an_unflagged_unsupported_claim(client, monkeypatch):
    model = DishonestModel()
    monkeypatch.setattr(llm, "chat_completion", model)
    failures, suggestions, clean, flagged, listed = {}, 0, 0, 0, 0

    for profile in PROFILES:
        user = create(profile)
        job = add_job(user, profile.job, nice=profile.nice)
        model.job = profile.job

        document = generate(client, user, job)
        found = unsupported(user.id, document)

        # Accept everything that can be accepted without confirming anything.
        for line in [line for line in document.lines() if line.rewrite]:
            response = client.patch(
                f"/tailored-resumes/{job}/versions/1", headers=auth(user.id),
                json={"lines": [{"line_id": line.id, "decision": "accepted"}]},
            )
            assert response.status_code == (409 if line.flags else 200), (profile.key, line.rewrite)
            suggestions += 1
            flagged += bool(line.flags)
            clean += not line.flags
        view = client.get(f"/tailored-resumes/{job}", headers=auth(user.id)).json()
        final = TailoredResumeDocument.model_validate(view["resume"]["document"])
        found += unsupported(user.id, final)
        found += [f"on the resume: {line.text!r}" for line in final.lines()
                  if _claims(line.text) != _claims(line.original)]
        for text in exported(client, user, job):
            found += [f"in a file: {word}" for word in ("Secret", "Hidden", "Elixir", "Someone else's", "75%",
                                                         "Architected", "Led the work")
                      if word in text]
        listed += len(final.skills)
        if found:
            failures[profile.key] = sorted(set(found))

    assert failures == {}
    # The gate saw something: the model tried every trick, and suggestions of both kinds appeared.
    assert model.used == set(WAYS)
    assert suggestions >= 8 and clean >= 1 and flagged >= 5 and listed >= 15


@pytest.mark.parametrize("broken", [unreachable, gibberish])
@pytest.mark.parametrize("profile", PROFILES, ids=[p.key for p in PROFILES])
def test_a_truthful_resume_still_comes_out_when_the_model_fails(client, monkeypatch, profile, broken):
    monkeypatch.setattr(llm, "chat_completion", broken)
    user = create(profile)
    job = add_job(user, profile.job, nice=profile.nice)

    document = generate(client, user, job)

    assert unsupported(user.id, document) == []
    assert all(line.rewrite is None and line.text == line.original for line in document.lines())
    # A notice says so whenever there was a bullet to send.
    sent = [line for entry in [*document.experience, *document.projects] for line in entry.bullets
            if any(_says(line.original, raw) or _says(line.original, canonical) for raw, canonical in profile.job)]
    assert document.notice or not sent
    for text in exported(client, user, job):
        assert "Casey Okafor" in text
        assert all(" ".join(line.text.split()) in text for line in document.lines())


def test_the_checker_catches_each_kind_of_false_statement(client, monkeypatch):
    """So that passing the gate means something."""
    monkeypatch.setattr(llm, "chat_completion", unreachable)
    profile = PROFILES[0]
    user = create(profile)
    truthful = generate(client, user, add_job(user, profile.job))
    assert unsupported(user.id, truthful) == []

    def tampered(change) -> list[str]:
        document = truthful.model_copy(deep=True)
        change(document)
        return unsupported(user.id, document)

    changes = {
        "name": lambda d: setattr(d.header, "full_name", "Someone Else"),
        "role": lambda d: setattr(d.experience[0], "role", "Principal Engineer"),
        "dates": lambda d: setattr(d.experience[0], "start_date_text", "2019"),
        "technology": lambda d: d.projects[0].technologies.append("Kubernetes"),
        "school": lambda d: setattr(d.education[0], "degree", "PhD"),
        "skill": lambda d: d.skills.append(SkillEntry(name="Kubernetes", canonical="kubernetes",
                                                      sources=d.skills[0].sources)),
        "original": lambda d: setattr(d.experience[0].bullets[0], "original", "Ran the department."),
        "rewrite": lambda d: setattr(d.experience[0].bullets[0], "rewrite", "Ran the department."),
        "invented role": lambda d: d.experience.append(ExperienceEntry(
            role="CTO", company="Nowhere", sources=[{"kind": "experience", "id": user.id}])),
    }
    for what, change in changes.items():
        assert tampered(change), what
