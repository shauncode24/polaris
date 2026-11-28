"""The tailored resume as the editor shows it, and the user's changes to it."""
from typing import get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import User
from app.schemas.resume.tailored import Link, Section, SourceRef, TailoredResumeDocument
from app.schemas.resume.tailored_editor import (
    CitedEvidence,
    ContactChange,
    EditorJob,
    ResumeChanges,
    ResumeEditorView,
    SavedResume,
)
from app.services.evidence.state import evidence_cutoff
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.contact import linkedin_profile_url, phone_number
from app.services.resume.grounding import ground_line
from app.services.resume.sources import cited_rows, row_bullets
from app.services.resume.tailored_score import score_resume
from app.services.resume.tailored_store import document_of, get_version, list_versions, save_document


class ResumeChangeError(Exception):
    """A change that can't be applied. The message is written for the user."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def source_key(ref: SourceRef) -> str:
    return f"{ref.kind}:{ref.id or ''}:{'' if ref.bullet is None else ref.bullet}"


def _sources(document: TailoredResumeDocument) -> list[SourceRef]:
    items = [*document.experience, *document.projects, *document.education, *document.skills, *document.lines()]
    return [ref for item in items for ref in item.sources]


_PROJECT_ORIGINS = {"github": "GitHub", "both": "Resume and GitHub"}


def _describe(kind: str, row) -> dict:
    """The title, origin, detail and link of one row of evidence."""
    if kind == "experience":
        return {"title": f"{row.role} at {row.company}", "origin": "LinkedIn" if row.source == "linkedin" else "Resume"}
    if kind == "education":
        return {"title": row.institution, "origin": "LinkedIn" if row.source == "linkedin" else "Resume",
                "detail": row.degree}
    if kind == "project":
        return {"title": row.name, "origin": _PROJECT_ORIGINS.get(row.source, "Resume"), "url": row.repo_url}
    if kind == "github_repo":
        technologies = ", ".join(row.technologies or [])
        return {"title": row.repo_name, "origin": "GitHub", "url": row.html_url,
                "detail": f"Found in the repository: {technologies}" if technologies else None}
    if kind == "certificate":
        return {"title": row.name, "origin": "Certificate", "detail": row.issuer}
    return {"title": "LinkedIn profile", "origin": "LinkedIn", "detail": "Listed in your LinkedIn skills"}


async def cited_evidence(db: AsyncSession, user_id, document: TailoredResumeDocument) -> dict[str, CitedEvidence]:
    refs = _sources(document)
    rows = await cited_rows(db, user_id, refs)

    def evidence(ref: SourceRef) -> CitedEvidence:
        if ref.kind == "leetcode_tag":
            return CitedEvidence(kind=ref.kind, title="LeetCode practice", origin="LeetCode")
        row = rows.get((ref.kind, ref.id))
        if row is None:
            return CitedEvidence(kind=ref.kind, title="Removed or hidden item", origin="Your profile", available=False)
        described = _describe(ref.kind, row)
        if ref.bullet is not None:
            bullets = row_bullets(ref.kind, row)
            described["detail"] = (bullets[ref.bullet] or "").strip() if ref.bullet < len(bullets) else None
        return CitedEvidence(kind=ref.kind, **described)

    return {source_key(ref): evidence(ref) for ref in refs}


async def editor_view(db: AsyncSession, user_id, job_intelligence_id, version: int | None = None) -> ResumeEditorView | None:
    """The user's resume for this job: the newest version unless one is named.
    None when the job isn't theirs or the named version doesn't exist.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None
    row = await get_version(db, user_id, job_intelligence_id, version)
    if row is None and version is not None:
        return None

    saved = None
    if row is not None:
        document = document_of(row)
        cutoff = await evidence_cutoff(db, user_id)
        saved = SavedResume(
            version=row.version, status=row.status, created_at=row.created_at,
            stale=cutoff is not None and row.created_at < cutoff,
            document=document, evidence=await cited_evidence(db, user_id, document),
            score=await score_resume(db, user_id, job, document),
        )
    return ResumeEditorView(
        job=EditorJob(id=str(job_intelligence_id), role=job.role, company=job.company),
        versions=await list_versions(db, user_id, job_intelligence_id),
        resume=saved,
    )


_CONTACT_FIELDS = {"phone": phone_number, "linkedin_url": linkedin_profile_url}


def _apply_contact(document: TailoredResumeDocument, contact: ContactChange) -> dict:
    """Puts the sent contact details in the header. Returns them as stored."""
    saved = {}
    for field, read in _CONTACT_FIELDS.items():
        if field not in contact.model_fields_set:
            continue
        try:
            saved[field] = read(getattr(contact, field))
        except ValueError as e:
            raise ResumeChangeError(str(e))
    header = document.header
    if "phone" in saved:
        header.phone = saved["phone"]
    if "linkedin_url" in saved:
        url = saved["linkedin_url"]
        header.links = [link for link in header.links if link.label != "LinkedIn"]
        if url:
            header.links.append(Link(label="LinkedIn", url=url))
    return saved


def apply_changes(document: TailoredResumeDocument, changes: ResumeChanges) -> dict:
    """Applies the user's choices to `document`, and returns the contact details
    to keep on their account. Raises `ResumeChangeError`, possibly after
    changing some of it, so a failed document must be discarded.
    """
    lines = {line.id: line for line in document.lines()}
    for change in changes.lines:
        line = lines.get(change.line_id)
        if line is None:
            raise ResumeChangeError("That line isn't on this resume. Reload the page.")
        if "edited" in change.model_fields_set:
            line.edited = " ".join((change.edited or "").split()) or None
        if change.decision is None:
            continue
        if change.decision == "accepted":
            ground_line(line)  # judged by today's rules, whatever was stored
            if not line.rewrite:
                raise ResumeChangeError("There is no rewording to accept on that line.")
            if line.flags and not change.confirm_flags:
                raise ResumeChangeError("Confirm that this rewording is accurate before accepting it.", 409)
        line.decision = change.decision

    if changes.section_order is not None:
        if sorted(changes.section_order) != sorted(get_args(Section)):
            raise ResumeChangeError("The section order must list every section once.")
        document.section_order = changes.section_order

    return _apply_contact(document, changes.contact) if changes.contact else {}


async def change_resume(
    db: AsyncSession, user_id, job_intelligence_id, version: int, changes: ResumeChanges,
) -> ResumeEditorView | None:
    """Saves the changes to that version, all or none, and returns it. None
    when the user has no such version.
    """
    # Locked until saved, so two changes at once don't overwrite each other.
    row = await get_version(db, user_id, job_intelligence_id, version, for_update=True)
    if row is None:
        return None
    document = document_of(row)
    try:
        contact = apply_changes(document, changes)
    except ResumeChangeError:
        await db.rollback()
        raise
    if contact:
        user = await db.get(User, user_id)
        for field, value in contact.items():
            setattr(user, field, value)
    await save_document(db, row, document)  # commits both
    return await editor_view(db, user_id, job_intelligence_id, version)
