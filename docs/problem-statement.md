# Polaris: Problem Statement and Core Scope

## Problem statement

**Job seekers in software engineering keep their proof of ability in many disconnected places.** Their projects are on GitHub, their experience is on a resume and LinkedIn, and their problem-solving record is on LeetCode. For each application they have to rebuild the case from scratch:

1. **Their evidence is scattered.** No single place records what they can actually demonstrate. Resumes drift from reality: they claim skills the repos don't back up, and they leave out strong work that never made it onto the page.
2. **Every job needs a different resume, and tailoring is manual.** People either send one generic resume or spend hours rewording it, with no check that the claims are true or that the right projects are leading.
3. **Interview preparation is generic.** Question banks aren't tied to the specific job or to the candidate's own history, so people practice the wrong topics and can't tell which of their real stories answers which question.

**Polaris** is a platform that holds a single, verified record of a candidate's evidence. For any job description, it then produces:
- a tailored resume that uses only claims the evidence supports
- a job-specific interview kit, with practice questions mapped to the candidate's own projects and experience, and the gaps called out

**One-line version:** *One verified source of truth about you, so any job description turns into a tailored resume and a targeted interview plan, without inventing a single claim.*

## Target user and context

- **Primary user:** an early- to mid-career software engineer or student applying to multiple roles, with a GitHub account, a resume and often a LeetCode history.
- **Moment of use:** they have a specific job description and want to apply and interview well in the next few days to weeks.
- **What they value:** accuracy (nothing that falls apart in an interview), speed (minutes, not hours, per application), and knowing what to practice.

## Product pillars (the core, in dependency order)

Everything else in the project exists to serve these four. If one of them doesn't work, the product doesn't work.

### Pillar 1: Unified evidence record (the source of truth)
**The system must hold one deduplicated, queryable record of what the candidate can demonstrate.**
- Ingest: resume (PDF/DOCX), GitHub (repos, languages, activity), LeetCode, LinkedIn (pasted text).
- **Projects come from every source.** A repo not mentioned on the resume still becomes a project candidate. A resume project with no repo is kept and marked "unverified". Matching is shared across sources, with user confirmation on uncertain matches.
- Every skill and claim carries **provenance**: which sources support it, with a confidence level.
- Users can **review and edit** the record (confirm, correct or remove items), and edits override automated extraction.
- Changes in one source update the record without duplicating entries.

*Done when:* adding a repo, uploading a new resume and editing a skill each update one coherent profile, with no duplicates and a visible source for each item.

### Pillar 2: Job-description understanding and fit
**Given a JD (pasted text or PDF), the system must say what it requires and how the candidate matches.**
- Structured extraction: role, company, seniority, required, preferred and implicit skills.
- Match against the evidence record: strengths, gaps, and how serious each gap is.
- Stored per JD, so the user can compare several jobs.

*Done when:* a real JD produces a stable structured profile and a match view that points to specific evidence for each matched requirement.

### Pillar 3: Tailored resume generation (the main output)
**For a chosen JD, the system must produce an actual resume the user can send.**
- Select and order the most relevant projects and experience from the **whole** evidence record, not just the last uploaded resume.
- Rewrite bullets to fit the JD's language, using only facts already in the record. Each rewritten line links back to its source, and unsupported claims are flagged or refused.
- The user can review, edit and accept changes line by line.
- Export to **PDF and DOCX**, in an ATS-safe layout. Save one version per JD.
- Show a before/after score (keyword coverage, ATS checks) so the improvement is visible.

*Done when:* from one JD, a user gets a downloadable resume in under a few minutes, and every claim in it traces to evidence.

### Pillar 4: Job-specific interview kit and practice
**For a chosen JD, the system must build a preparation plan from the candidate's own evidence.**
- Generate a question set by category (technical depth, system design, behavioral, role-specific) from the JD's requirements and seniority.
- For each question: which of the candidate's projects or experiences best answers it, a suggested answer outline built from their real facts, and **warnings where evidence is thin**.
- A practice mode: the user answers, gets feedback grounded in their own record, and the system tracks coverage ("12 of 20 practiced, weakest area: system design").
- A study plan for gaps that links to the LeetCode topics and skills the JD needs.

*Done when:* from one JD, a user gets a categorized question list, each question tied to specific evidence or an explicit gap, and can practice and see progress.

## The core user journey (the one flow that must always work)

```
Connect sources (resume, GitHub, LeetCode, LinkedIn)
        ↓
Review & confirm the unified profile
        ↓
Add a job description
        ↓
See fit + gaps
        ↓                        ↓
Generate tailored resume     Generate interview kit
(review, edit, export)       (practice, track progress)
```

This journey is the acceptance test for the whole product. It should run end to end as one automated test with a stubbed LLM, and as one manual run with a real LLM before any release.

## Trust requirements (what "verified" means)

These are part of the problem, not extras. The product's value is that it never says something untrue about the user.
- **No fabrication.** Generated resume lines and interview answers may only use facts in the evidence record. Anything else must be flagged as a suggestion for the user to confirm.
- **Traceability.** Any generated claim can be expanded to show its source.
- **User control.** Nothing is overwritten or exported without the user seeing it.
- **Graceful failure.** If the LLM is down, the user still gets the deterministic parts (matching, ranking, gaps) with a clear notice.
- **Data ownership.** The user can delete their data. Private data is isolated per account. (The cross-user lookup bug from the audit must be fixed before anyone else uses this, since it breaks this requirement.)

## Scope

**In scope (v1)**
- The four pillars above and the journey that connects them.
- Sources: resume, GitHub, LeetCode, LinkedIn paste.
- Software-engineering roles.
- Minimum viable security and reliability: user-scoped data, auth that doesn't leak tokens, LLM calls that time out and retry, and CI that runs the end-to-end test.

**Out of scope (v1)**
- Non-engineering careers.
- Job search, job board scraping, or auto-applying.
- LinkedIn scraping (paste only, as built).
- Mobile apps, team or recruiter accounts, payments.
- Live mock interviews with voice or video.

**Existing features that are secondary** (keep, but don't invest until the core works): dashboard nudges, weekly briefs, the career planner's daily plans, and the Identity page's detailed analytics. They can stay as they are or be simplified.

## Success criteria

| Measure | Target |
|---|---|
| Journey completion | A new user reaches a tailored, exported resume and an interview kit in under 15 minutes, from a fresh account |
| Truthfulness | 0 unsupported claims in generated resumes across a test set of at least 10 profile and JD pairs |
| Evidence coverage | Every generated bullet links to at least one source record |
| Repeatability | The journey test passes in CI on every change |
| Resilience | With the LLM stubbed to fail, every pillar still returns its deterministic output without a 500 |

## Gap against the codebase (as of the audit)

| Pillar | Today | Gap |
|---|---|---|
| 1. Unified record | Resume-centric; GitHub is evidence only (`Project` rows are created only in `services/resume/ingestion.py`) | Create projects from GitHub, shared dedupe, user review and edit |
| 2. JD understanding | Implemented (`services/job_intelligence`, `services/skill_gap`) | Verify it end to end, tie matches to evidence |
| 3. Tailored resume | Advisory report only (`services/resume/tailoring_llm.py`) | **Build** bullet rewriting, grounding checks, editor, PDF/DOCX export, per-JD versions |
| 4. Interview kit | Reactive coach for typed questions (`api/interview.py`) | **Build** JD-driven question generation, evidence mapping, practice tracking |
| Journey test | None | Build |

## Build order

1. **Baseline run:** run the current journey by hand to see what breaks (½ day).
2. **Pillar 1:** GitHub-sourced projects and unified review/edit.
3. **Pillar 2:** verify, and expose evidence for each match.
4. **Pillar 3:** the tailored-resume generator and export. This is the largest piece.
5. **Pillar 4:** the interview kit and practice tracking.
6. **Journey test in CI,** written early and extended as each pillar lands.
7. **Minimum trust fixes,** in parallel with step 2: user scoping on ID lookups (`get_job_intelligence`, cached claim audit and interview questions) and removal of the token-in-URL download auth. The rest of the hardening (rate limits, background jobs, deployment) follows once the core works.
