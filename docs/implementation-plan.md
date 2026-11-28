# Polaris: Implementation Plan (Today → Deployment)

This is the complete, ordered plan to take Polaris from its current state to a deployed, usable product, as defined in [problem-statement.md](problem-statement.md). Steps are numbered in the order they should be done. Nothing outside this list is required for launch. Anything not listed (new features, secondary pages) is explicitly deferred.

Estimates assume one developer working part-time and are rough. Total: about **10–12 weeks**.

## Progress

Updated after step 38. Unmarked steps (39 to 71, plus 6 and 13) are not started.

| Stage | Status | Steps |
|---|---|---|
| A. Baseline and safety net | ◐ partly done | 1, 2 done; 5 partial; 3, 4 skipped; 6 not started |
| B. Consolidate and make the data trustworthy | ✅ done except step 13 | 7 to 12 done (committed in `82bac8a`); 13 not started |
| C. Unified evidence record | ✅ done | 14 to 20 done (committed) |
| D. JD fit tied to evidence | ✅ done | 21 to 24 |
| E. LLM foundation | ✅ done | 25 to 28 |
| F. Tailored resume | ✅ done | 29 to 37 |
| G. Interview kit and practice | ◐ in progress | 38 done; 39 to 43 not started |
| H. Hardening and account basics | not started | 44 to 51 |
| I. Frontend quality | not started | 52 to 57 |
| J. Deployment | not started | 58 to 67 |
| K. Beta and launch | not started | 68 to 71 |

**33 of 71 steps done, 1 partial, 2 skipped, 35 not started** (33 of them in Stages G to K).

Legend: ✅ done and verified as described, ◐ partly done, ⏭ skipped on purpose. Tests: 865 pass against a throwaway database; the frontend builds.

### Where the work differs from the plan

- **Extended instead of added.** The evidence review lives in the existing My Profile page; no new page was created (step 18).
- **Timestamp instead of stale flags.** Out-of-date reports are detected by comparing against `users.evidence_updated_at`, not by a flag on each report (step 20).
- **Hide, then dedupe order.** Items are deduplicated first, newest wins, and only then hidden ones are dropped; otherwise hiding the newest copy would bring back an older upload.
- **Added, not in the plan.** A database-backed test setup (`TEST_DATABASE_URL`, rebuilt from the migrations on every run), a mutation check of the tests, and `docs/user-actions.md`.
- **Still needs you.** Applying the migrations to Neon, a hosting choice, the real-LLM run, and a look at the profile page: see `docs/user-actions.md`.

## Decisions to make before step 1

Recommended choice in bold.

| Decision | Options | Affects | Status |
|---|---|---|---|
| Hosting | **Render or Fly.io with managed Postgres**, or one VPS with Compose | Steps 13 and 58 to 67 | open |
| LLM provider | **Keep Groq, behind a provider setting**, or switch | Steps 25 and 31 | Groq kept (step 25); budget and daily limit still open |
| Resume export | **One structured resume JSON rendered to DOCX (`python-docx`) and PDF (ReportLab)** | Steps 29 to 36 | ReportLab chosen for PDF |
| Background work | **FastAPI tasks plus a `jobs` table**; Celery/RQ only if needed | Steps 26 and 27 | open |
| Legacy `JobDescription` rows | **Migrate any worth keeping, then drop the table** | Step 7 | ✅ done |
| Transactional email (password reset) | **A hosted provider such as Resend or Postmark** | Step 46 | open |
| Secondary features (dashboard nudges, weekly brief, planner, Identity page) | **Frozen: only unbreak or delete, no new work** | all | open |

## Stage A: Baseline and safety net (about 2 days) — ◐ partly done

✅ 1. Run Postgres locally in Docker. Run `alembic upgrade head` on an empty database to confirm the migration chain.
   - **Status:** Done. Built the full migration chain on an empty pgvector Postgres in Docker, and ran upgrade/downgrade cycles on it. `docker-compose.yml` still has no database service (Stage J).
✅ 2. Add `GROQ_API_KEY`, `GROQ_BASE_URL` and `GROQ_MODEL` to `.env.example`. Remove the Ollama and Gemini variables that no code reads.
   - **Status:** Done. `.env.example` now lists the Groq variables, the Ollama ones are gone, and it documents `TEST_DATABASE_URL`. The commented-out clients in `core/llm.py` are still there (step 25).
⏭ 3. Walk the current journey by hand with a real key: register, upload a resume, sync GitHub, sync LeetCode, add a JD, skill gap, tailoring, interview. Write every failure into `docs/known-issues.md`.
   - **Status:** Skipped by choice. Still worth doing once with a real `GROQ_API_KEY`: everything verified so far used a stubbed or absent LLM. Tracked in `docs/user-actions.md`.
⏭ 4. Confirm the JD seam: add a JD through the Job Intelligence page and check whether the Resume, Career Planner, Interview and Dashboard pages list it.
   - **Status:** Skipped. Not observed live. The seam was confirmed from the code and fixed in step 7.
◐ 5. Repair CI (`.github/workflows/tests.yml`): Linux runner, Postgres service, dummy values for `DATABASE_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, run `alembic upgrade head` before tests, and add a frontend job running `npm ci` and `npm run build`. Delete `tests/test_placeholder.py`.
   - **Gate:** CI is green on a clean clone. ◐ CI not run; the test suite no longer depends on env vars.
   - **Status:** Partly done. Test setup no longer needs env vars (`tests/conftest.py` supplies safe defaults), so CI should stop failing for that reason. The workflow itself is unchanged: still Windows, no Postgres service, no frontend job, and `tests/test_placeholder.py` still exists.
6. Write the journey test skeleton in `backend/tests/journey/test_core_journey.py`: async client, test database, stubbed `chat_completion`, with the steps that don't work yet marked `xfail`. Every later step extends this test.
   - **Status:** Not started. Not started. The pieces it needs now exist: `tests/api/` has a seeded test database, an authenticated client and the migration rebuild.

## Stage B: Consolidate and make the data trustworthy (1–1.5 weeks) — ✅ done, except step 13

✅ 7. **Finish the JD migration.** Make `JobIntelligenceProfileRow` the only JD record.
   - Migrate or drop legacy `JobDescription` rows (back up the database first and review row counts).
   - Re-key tailoring, resume analysis, career planner, interview and dashboard on the new record. Files: `api/jobs.py`, `api/resume.py`, `services/resume/tailoring_llm.py`, `services/career_planner/context_builder.py`, `models/facts.py`, `frontend/src/api/jobs.js`, and the Resume, Planner, Interview and Dashboard pages.
   - Remove `/jobs/analyze`, `/jobs/analyze-pdf`, `/jobs/{id}`, `GET /jobs`, the dual-write, and the unused `analyzeJobText`, `analyzeJobPdf` and `getJobAnalysis`.
   - **Status:** Done. Committed in `82bac8a`. Migrated by direct link or text hash and tested on seeded data covering every case; the downgrade restores structure, not data. Not yet applied to Neon.
✅ 8. Scope every ID lookup by `user_id`: `get_job_intelligence`, `get_cached_claim_audit_report`, `get_cached_interview_questions`, then sweep every `where(X.id ==` in the codebase.
   - **Status:** Done. Committed in `82bac8a`. The claim-audit, interview-question and tailoring caches are now scoped by user too (the coherence cache followed in step 20).
✅ 9. Add the authorization test matrix: every route that takes an ID, called as another user, must return 404.
   - **Status:** Done. Committed in `82bac8a` with 16 routes (19 cases now that the profile routes are covered), plus a meta-test that fails when a new route with an ID has no case. Verified by reintroducing the original bugs.
✅ 10. Remove `?token=` authentication. The resume preview fetches with a header and uses a blob URL. Delete `get_current_user_from_query`.
    - **Status:** Done. Committed in `82bac8a`.
✅ 11. Treat a malformed token `sub` as 401. Wrap all three PDF-parsing call sites so a corrupt file returns 400, and run parsing off the event loop. Sanitize the download filename. Stop logging emails.
    - **Status:** Done. Committed in `82bac8a`.
✅ 12. Delete confirmed dead backend code: `services/resume/ats_checks.py` and its import, `core/config.py`, `services/career_planner/practice_modes.py`, the ORM models `AgentFeedback`, `GoalEvent`, `ReadinessScore`, `Embedding`, `CapabilityRequirement` (with a migration dropping their tables), `models/retrieval.py` and the unused pgvector dependency, `backend/ollama/`, and the other unreferenced definitions the audit listed. Review each remaining unused definition before deleting.
    - **Gate:** the authorization matrix and the JD steps of the journey test pass in CI, and a JD added in the UI appears in every picker. ◐ Authorization matrix passes locally (not in CI); the journey test does not exist yet. The JD flow is fixed in code but not seen in the UI.
    - **Status:** Done. Committed in `82bac8a`, with two deviations: the `pgvector` dependency stays because the first migration imports it, and `services/projects/curation.py` (used only by tests) and `app/scripts/clear_db.py` (truncates every table in the configured database) were left for you to decide.
13. Stand up a staging environment now, even if rough, and deploy to it from CI, so deployment problems surface early. (The production work remains in Stage H.)
    - **Status:** Not started. Not started. Needs your hosting choice and an account (`docs/user-actions.md`).

## Stage C: Pillar 1, unified evidence record (about 1.5 weeks) — ✅ done (UI not yet seen in a browser)

✅ 14. Add `source` (resume, github, both) and a shared dedupe key to `Project` (`models/facts.py`, new migration, reusing `normalize_name` and the repo URL).
    - **Status:** Done. `source` is now set to resume, github or both, and a `dedupe_key` that edits never change was added, plus review state and hide flag on projects, experiences and education (migration `d3a7b5c9e1f2`).
✅ 15. Create or merge `Project` rows from analyzed repos during GitHub sync (`services/github/github_sync.py`, `services/projects/repo_linking.py`). Uncertain matches go into a "needs confirmation" state.
    - **Status:** Done. `services/projects/reconcile.py`, idempotent, runs after a GitHub sync, a resume upload and a link change. Exact matches link automatically; near matches stay as suggestions for the user to confirm, and unlinking is remembered.
✅ 16. Merge the six confidence and evidence modules into one reader (`services/resume/confidence*.py`, `services/identity/*confidence*.py`, `services/evidence.py`, `services/resume/analysis/evidence.py`). First add characterization tests that capture current outputs, so the merge is checked against them.
    - **Status:** Done. Six modules became three in `services/evidence/`, after pinning the old numbers in tests, none of which changed. `services/resume/analysis/evidence.py` was deliberately left alone: it measures something different (source counts on the resume), not confidence.
✅ 17. Expose provenance on every skill, project and experience (which sources support it, with confidence) through the API (`api/profile.py`).
    - **Status:** Done. `/profile/data` returns each item's sources and review state, and every skill's confidence, sources and flags.
✅ 18. Build the evidence review page: confirm, edit or hide any project, experience or skill. User edits override extraction and survive re-sync.
    - **Status:** Done. Built into the existing My Profile page instead of a new page, and driven by the server record. Confirm, edit, hide and restore work for projects, experiences, education and skills, and decisions survive GitHub re-syncs and resume re-uploads. Verified by tests and a successful build; **not yet seen in a browser**.
✅ 19. Mount the LinkedIn import panel and the LinkedIn workspace view, and merge LinkedIn roles into the review page (`components/profile/LinkedInImportPanel.jsx`, `pages/ProfilePage.jsx`).
    - **Status:** Done. The panel is mounted and shows the last import. LinkedIn roles appear in the Experiences card with a LinkedIn badge. Not seen in a browser.
✅ 20. When evidence changes, mark dependent tailored resumes, claim audits and interview kits as stale (`services/identity/identity_refresh.py`).
    - **Gate:** a repo missing from the resume appears as a project candidate, re-sync creates no duplicates, every item shows its source, and a user edit survives a re-sync. The journey test covers this. ◐ Met by automated tests (GitHub-only projects appear, re-sync adds no duplicates, every item shows its source, edits survive). Not checked by a journey test or in a browser.
    - **Status:** Done. Implemented as an evidence timestamp (`users.evidence_updated_at`) that cached reports are compared against, covering tailoring, claim audit, interview questions, coherence and portfolio narrative. Tailored resumes and interview kits don't exist yet, so steps 29 to 43 must use the same check. `identity_refresh.py` was not changed.

## Stage D: Pillar 2, JD fit tied to evidence (about 1 week) — ✅ done (UI not yet seen in a browser)

✅ 21. For every matched requirement, return the specific project, bullet or LeetCode topic that supports it. Gaps return a severity.
    - **Status:** Done. Every met requirement carries the projects, bullets, repos and LeetCode topics behind it; every missing or partial one carries a severity (critical, moderate, minor); weak evidence is shown for near misses; the Skill Gap page displays both. Fixed on the way, because step 21's output depends on them: the skill gap ignored hidden skills and the claim-risk discount; evidence from hidden items and from superseded uploads still counted (re-uploading inflated scores); resume ingestion attached evidence to the wrong role when a role had several matching bullets; stored comparisons were never rebuilt after the evidence changed. Verified by tests; **not yet seen in a browser**. Known limits: editing a project's technologies does not change which skills it counts for, and role-fit and resume analysis still read raw evidence rows.
✅ 22. Run JD extraction on 5–10 real job descriptions and fix prompts or normalization where skills are missed or invented.
    - **Status:** Done. Ran 10 real software postings through the pipeline with the real model and scored them against skills written down beforehand: 96 of 141 (68%) before any change. The main fault was replies cut off partway (5 of 10) and saved as if complete; they are now detected, asked for again, and fail loudly if still incomplete, with lower reasoning effort so they fit. Also fixed: entries bundling several skills, one skill under several names, soft skills and candidate history listed as requirements, inferred skills resting on invented quotes, and prompt gaps. After the fixes, 123 of 141 (87%) across all 10; the GitLab posting went from 2 of 16 to 15. Two of the ten (20 of 28 between them) were last measured just before the final two filters, because their rerun hit Groq's daily limit. These postings were also used to tune the fixes, so the score is optimistic for new ones. Known limits: some duty phrases and long "nice to have" sentences still come through, a skill is occasionally put in the wrong band or missed, and results vary a little between runs. Rerun with `app/scripts/eval_jd_extraction.py`.
✅ 23. Build the JD library: list, compare, delete, and mark one as the primary target that the planner and interview read.
    - **Status:** Done. The Job & Company Intel page is now the library: open, delete, tick two to four jobs to compare (match score per job, then one table of skills showing your standing and how each job asks for it), and set one as the primary target (migration `f1a7c3e9b5d2`). The planner uses a goal's own job, then the primary target, then the last compared job, and always works from your current evidence. Interview practice uses the job chosen for the session, then the primary target, then the active goal's job, and no longer mixes a typed role with another job's requirements; a corrected answer keeps its job. The primary target is listed first, so pages that default to the first job now default to it. Deleting a job removes its comparisons and tailoring advice and keeps goals, without the link. Verified by tests and a successful build; **not yet seen in a browser**.
✅ 24. Unify the skill-gap response models, and delete the orphaned jobs components (`JobAnalysisResults`, `JobDescriptionForm`, `PastAnalysesPanel`, `HistoryPopover`, `AnalyzingProgress`) after copying anything `SkillGapResults` lacks.
    - **Gate:** a real JD gives a match view where every "met" requirement links to evidence. ✅ Checked on 9 saved real postings against a sample record: all 19 met requirements carried their projects, experience, repos or LeetCode topics. Not checked in a browser; only GitHub items are clickable.
    - **Status:** Done. The skill-gap models live in one module with a shared base for the three kinds of match (stored comparisons are rebuilt once), and the unused response model is gone. The five components and the two only they used are deleted; the Skill Gap page gained strengths and risks, links to plan and practise for that job, and match scores in the job picker. The job list now shows a score only while it is current. **Added to this step:** LeetCode practice counts toward "data structures" and "algorithms": 100 solved problems across 5 topics meets the requirement, 30 across 3 meets it partly, and less is shown as weak evidence.

## Stage E: LLM foundation (about 3–4 days) — ✅ done

This comes before the two large generation features, because they depend on it.

✅ 25. Build one `llm_json(prompt, schema, fallback)` helper in `core/llm.py` with a timeout, bounded retries with backoff on 429 and 5xx, token and latency logging, and a clear error when the key is missing. Remove the commented-out clients and the Ollama prefill hack, or put them behind an explicit `LLM_PROVIDER` setting.
    - **Status:** Done. All 25 model calls go through `llm_json`: 60-second timeout, two retries on rate limits, server errors and dropped connections, one more attempt for a reply that is unreadable or cut off (each call names the sections a finished reply has), a log line with tokens and time, error messages that are safe to show, and the caller's fallback. The commented-out clients and the Ollama workaround are removed; no provider setting was added. Fixed on the way: **interview practice and identity summaries named a model the Groq account doesn't offer**, so they could not succeed; a cut-off resume upload was saved as complete; a skill the model skipped, or a failed tagging call, was remembered as a real answer; provider error text could reach users; and the test suite could call the real model. Verified by tests. Against the real model, only question classification and answer planning have been tried (both accepted first time); **the other calls have not**, because the daily limit was reached.
✅ 26. Add the `jobs` table and a status endpoint (`GET /jobs/{id}/status` under a new name that doesn't collide with the removed JD routes). Long LLM work returns 202 plus a job ID, and the frontend polls.
    - **Status:** Done. Table `background_jobs`, status route `GET /background-jobs/{id}`. Job analysis, skill gap, career plan, interview answers and corrections, resume upload, review, analysis, coherence and tailoring, GitHub sync and review, LeetCode review, LinkedIn import, the project reports, identity refresh and weekly brief now answer 202 and finish in the background; stored results and input errors are still answered at once. The frontend waits through one shared helper (`apiFetch`), so the pages did not change. Jobs run inside the server process (no separate worker): a restart fails the running ones, which are then reported as interrupted; an identical request joins the running job; a job is stopped after 15 minutes; finished jobs are cleared after a day. Still answered in the request: the resume page's role-fit call when no analysis is stored, and a LeetCode sync's classification of topic names not seen before. Verified by tests and by running the frontend helper against a local server; **not tried in a browser**.
✅ 27. Add an advisory lock so only one identity refresh runs per user at a time. Move `trigger_identity_refresh` onto a background job.
    - **Status:** Done. Every data change (resume upload and analysis, syncs, LinkedIn import, project link and unlink, claim audit, skill gap) now starts the identity refresh as its own background job, so the request no longer waits for it. A Postgres advisory lock allows one refresh per user at a time, across server processes. Changes made during a refresh get exactly one further refresh; a snapshot is now dated by when its data was read so that this can be told. The manual refresh uses the same lock. **Known limits:** pages show the previous identity until the refresh finishes (a new user sees none for those seconds); a running refresh holds two of the server's 15 database connections, so many simultaneous users would need a larger pool (Stage J). Verified by tests; not tried in a browser.
✅ 28. Add a per-user daily LLM call budget with a clear error when it's reached.
    - **Status:** Done. Each user gets 100 model calls per UTC day (`LLM_DAILY_CALLS_PER_USER`; 0 removes the limit), counted in the `llm_usage` table where every call is made, so requests, background jobs and identity refreshes all count. Calls the service never answered are given back. At the limit, new AI work is refused with a message saying so; saved results, page loads and the GitHub and LeetCode syncs still work. **Known limit:** work that starts with calls left but runs out partway fails with the same message in most features; a skill gap, career plan or resume review may instead finish with its non-AI fallback, marked as such. The limit counts calls, not tokens. Verified by tests; not tried in a browser.

## Stage F: Pillar 3, tailored resume (about 2–2.5 weeks) — ✅ done (not yet tried with a real profile)

New tables: `TailoredResume` (user, JD, version, structured JSON, status, created_at), with `evidence_refs` on each line.

✅ 29. Define the structured resume schema: header, summary, experience (role, company, dates, bullets), projects, education, skills. Every bullet carries `source_ids`.
    - **Status:** Done. `TailoredResumeDocument` in `schemas/resume/tailored.py`; the references are called `sources` (kind, row id, bullet number) and every line, entry and skill needs at least one. Each line keeps the original wording, an AI rewrite, the user's decision and any edit; **a rewrite appears only once accepted**. Table `tailored_resumes` stores numbered versions per job, and deleting a job deletes them (`services/resume/tailored_store.py`). Nothing generates or shows a resume yet. Not yet checked: that referenced rows exist and belong to the user (needed before the editor can send a document, steps 32 and 34).
✅ 30. Selection: reuse `rank_items_for_jd` over the whole evidence record (resume, GitHub, LinkedIn), keeping the claim-risk penalty.
    - **Status:** Done. `select_for_job` in `services/resume/selection.py` builds a `TailoredResumeDocument` in the evidence's own wording, with a ranking that says why each item was chosen. No model calls; nothing calls it yet. Up to 4 roles (most relevant, in resume order) and 4 projects (relevant ones, topped up to 2), bullets that show the job's skills first, and up to 18 skills the user has evidence for, required ones first. Hidden items and skills are left out; LeetCode practice alone lists a skill only when the job asks for it. **Limits:** a project description is one bullet per line, so a paragraph stays one bullet; a claim-audit penalty is lost after a resume re-upload until the project is audited again. **Gap found and fixed afterwards:** resume and LinkedIn imports discarded start and end dates. They are now saved with the wording as written (`services/resume/dates.py`), which is what a resume shows, so a stated year never becomes a month. This also switches on two checks that had no dates to work with: the note (and lower skill score) when GitHub evidence starts long after a role ended, and the resume analysis's role order and overlap points. Rows imported earlier have no dates until imported again.
✅ 31. Bullet rewriting: the LLM rewrites each selected bullet toward the JD's language, given only that bullet's source facts, through `llm_json`.
    - **Status:** Done. `rewrite_bullets` in `services/resume/rewriting.py` makes one call per experience or project bullet. A call holds the bullet's own wording and the job's names for the skills that bullet already mentions: no role, company, other bullet or other requirement. Rewrites are stored as pending suggestions, so the resume keeps the original wording until the user accepts one. A bullet that mentions none of the job's skills is not sent, since there is no job wording to move it toward; education lines are not rewritten and no summary is written. An unusable reply skips that bullet, an unavailable model stops the run, both are reported in `problem` (for step 33's notice), and the daily limit raises as elsewhere. Nothing calls it yet. Verified by tests and by rewriting 13 made-up bullets with the real model. **For step 32:** after the prompt was tightened, the model still named something the bullet didn't in 3 of the 13 ("version control" became "Git", "containerised" became "Dockerized", "data warehouse" became "Redshift"; the last two pairings were made up for the test). The gate must compare against the bullet's literal wording: matching by skill name would pass "Git", because "version control" counts as Git. It also saw one rewrite read worse than its original.
✅ 32. Grounding gate: every number, technology and claim in a rewritten bullet must exist in its source facts. Violations are dropped or flagged "needs your confirmation". Reuse the approach in `services/interview/grounding.py`.
    - **Status:** Done. `services/resume/grounding.py`, deterministic, applied to every rewrite as it is made. It compares the rewrite with the bullet's literal words, not with skill names. A figure the bullet doesn't state removes the rewrite. Any other word added or left out, a changed symbol (`~`, `+`, `$`), or the same words in a new order, is kept and flagged in the line's `flags`, in words for the user. Only listed spellings of one name pass ("Postgres" and "PostgreSQL", "AWS" and "Amazon Web Services"). `unsupported_sources` checks that everything a document cites exists, is the user's and is not hidden, and that each line's original is the cited bullet. Of the 10 changed rewrites saved from step 31's real-model runs, 3 passed and 7 were flagged, including every unsupported one; at least one flagged rewrite was a fair paraphrase. **Limits:** fair paraphrases and reorderings are flagged too, so most real rewording will ask for confirmation; ordinary punctuation, hyphens, slashes and capital letters are not compared; entry headings, technologies and skill names are not compared with their sources. **For step 34:** run `ground_line` on every line and `unsupported_sources` on any document the browser sends (nothing calls the latter yet), and make accepting a flagged rewrite an explicit confirmation.
✅ 33. Deterministic fallback: if the LLM fails, return the original bullets ordered by relevance with a notice.
    - **Status:** Done. `generate_tailored_resume` in `services/resume/generation.py` chooses the evidence, asks for rewrites, and never raises a model failure: the resume keeps the user's wording, the bullets most relevant to the job first, and a new `notice` field on the document says what happened and why. It covers a missing key, rate limits, server errors, timeouts, unreadable replies and a used-up daily limit. Rewrites made before a failure are kept, and the notice then says only some bullets were reworded. **Changed from step 31:** running out of the day's calls partway no longer raises, so those rewrites aren't lost; and three unusable replies in a row now end the run. Nothing calls it, saves its result or shows the notice yet (step 34). Verified by tests with a stand-in model.
✅ 34. Editor UI: original against rewritten, per-bullet accept, reject or edit, section reordering, evidence shown for each line.
    - **Status:** Done. A new Tailored Resume page (`/tailored-resume`, in the sidebar and linked from the Skill Gap page): generate for a saved job, compare each suggestion with the original, accept, reject, undo or edit each line, move sections, and open the evidence behind any line, entry or skill. A flagged suggestion can only be accepted after confirming it is accurate, which the server enforces. The notice from step 33 and an out-of-date warning are shown; each generation is a new version and earlier ones stay available. New routes under `/tailored-resumes/{job}`. **Instead of step 32's plan:** the browser sends only the user's choices, never a document, so original wording, sources and flags can't be altered from outside and nothing needs `unsupported_sources` on the way in (it still has no caller). Generating works with the daily limit used up, giving the user's own wording. Verified by tests, a frontend build, and a headless-browser run against a throwaway database with a stand-in model (light, dark and a 600px window); **not tried with the real model or your own profile**. **Not editable:** name, email and location, entry headings, the skills list and bullet order, and a bullet can't be removed from the resume (phone and LinkedIn were added after step 35).
✅ 35. Scoring: before and after keyword coverage and ATS checks, using the `analysis` engine on the generated resume.
    - **Status:** Done. The Tailored Resume page compares the resume with the latest uploaded one: how many of the job's required and implied skills each names (and which were gained or lost), the engine's ATS score with its six parts, and the warnings on the tailored one. `services/resume/tailored_score.py` renders the document as plain text and runs the existing ATS and keyword checks on both. No model calls, nothing saved; the score changes as suggestions are accepted or lines edited. Verified by tests, a frontend build and a headless-browser run on made-up data. **Limits:** keywords match only in the job's wording ("Postgres" doesn't count for "PostgreSQL"); the ATS rules are the engine's heuristics, not a real screening system. **Fixed afterwards:** a listed skill now takes the job's spelling when both are the same name (the list from step 32, now `services/resume/skill_names.py`; a different term is never swapped in; project technologies keep the user's spelling, and saved versions change only when generated again). Phone number and LinkedIn link can be edited under the name; they are checked, saved to the account (migration `e1b6c3d8f5a2`) and used for later versions. The ATS phone rule now finds numbers it missed, such as `+91 98765 43210` and `+44 20 7946 0958`, and needs at least 9 digits, so scores of uploaded resumes can change too. **For step 36:** the tailored side is scored from plain text, not from the exported file; check that text extracted from the export scores the same.
✅ 36. Export: DOCX through `python-docx`, PDF through ReportLab, both in an ATS-safe single-column layout built from the same structured resume. Bundle a font file so accented names and symbols display correctly. Store a version per JD. Prove the PDF export inside the Docker image now, not at deployment.
    - **Status:** Done. The Tailored Resume page downloads the open version as PDF or Word (`GET /tailored-resumes/{job}/versions/{n}/export`). Both, and the score, are built from the same text blocks (`services/resume/render.py`), so they hold the same words in the same order; text read back from either file scores the same as the editor shows. Only approved wording is exported, and the page says when suggestions are still waiting or cited items have been removed or hidden. The PDF embeds DejaVu Sans (`app/assets/fonts`, with its licence). Versions per job were already stored (step 29); files are made on request and not kept. A `.dockerignore` was added. Verified by tests, a headless-browser run, the export tests and a sample PDF inside the backend image with networking off, and a LibreOffice rendering of the Word file; **not opened in Microsoft Word**, and the frontend image was not rebuilt. **Limits:** the PDF refuses, with a message, characters the font lacks (Chinese, Devanagari and other scripts, emoji) and right-to-left text, while the Word file takes them; A4 only; editing a version after downloading it changes what that version downloads, so what was sent isn't kept.
✅ 37. Retire the advisory tailoring report: fold its ranking into the generator and remove the old endpoint and `ResumeTailoring` component.
    - **Status:** Done. The endpoint `/resume/tailor/{job}`, its report, prompt, schemas and the `ResumeTailoring` panel are removed, the ranking now lives in `services/resume/selection.py`, and the Resume page links to the Tailored Resume page. Migration `f2c7d4e9a1b3` drops the cache table `resume_tailoring_reviews` (the downgrade restores it empty).
    - **Gate:** zero unflagged unsupported claims across 10 profile and JD test pairs (an automated test diffs facts against sources), and the output still works with the LLM stubbed to fail. ✅ `tests/api/test_resume_gate.py`: ten made-up profile and job pairs, a stand-in model that tries nine ways of overstating, and a separate checker that compares every fact on each resume and in each download with the database; all ten also pass with the model unreachable or answering nonsense. **The first run failed on four profiles:** skills were listed under names from the table shared by all users, so a resume could show another person's spelling, or keep a skill since removed from an item. Fixed: a skill is now named as a source it cites names it, and is left off when the record no longer says it. Switching off the rewrite check also makes the gate fail. **What it doesn't show:** the pairs are made up, no real model was used, and the word-for-word rule it checks can't judge punctuation.

## Stage G: Pillar 4, interview kit and practice (about 1.5–2 weeks) — ◐ in progress

New tables: `InterviewKit` (user, JD), `InterviewQuestion` (category, text, evidence refs, gap flag), `PracticeAttempt` (answer, feedback, score).

✅ 38. Question generation from the JD's requirements, `interview_focus_areas` and seniority: technical depth, system design, behavioral, role-specific. Validate against a schema. A deterministic topic skeleton is the fallback.
    - **Status:** Done. `build_outline` in `services/interview/kit_outline.py` decides from the job alone what is asked: each question's category, topic, job skills and competencies, with a standard wording. The seniority sets how many: 15 (intern) to 21 (staff), fewer when the job gives less to ask about. `generate_interview_kit` (`kit_generation.py`) makes one model call to word them, sending only the job, never anything about the candidate. The model can't add, drop or retag a question; a wording that is missing, too short or long, repeated, or (for technical depth) doesn't name its skill leaves the standard one, and the kit's `notice` says so. A missing key, an outage, unreadable replies or a used-up daily limit give the whole kit in standard wording. Tables `interview_kits` and `interview_questions` (migration `a3d8e5f0b2c4`) store numbered versions per job, so a new kit keeps earlier questions; deleting a job deletes them (`kit_store.py`). Nothing calls it yet. Verified by tests with a stand-in model, and by wording kits for 5 saved real postings with the real model: every call was accepted first time and 4 kits had every question worded; the intern one kept 2 of 15 standard because the model reworded the skill's name. Those trial jobs were rebuilt from saved extraction replies, without skill normalization. **Limits:** standard wording reads stiffly with some topics; wording quality is not checked (one reply had a garbled word); a technical question is rejected if it shortens the skill's name; questions don't use company notes. `PracticeAttempt` is left to step 41. **For step 39:** fill `evidence_refs` and `thin_evidence` (empty until then), using each question's `skills` and `competencies`, and compare the kit's date with `evidence_cutoff` (step 20).
39. Evidence mapping: for each question, choose the best project, experience or LeetCode topic using the existing interview context-builder ranking. Mark "thin evidence" when none qualifies.
40. Answer outline built only from mapped facts, passed through the existing grounding gate.
41. Practice mode: the user answers a question and the existing `/interview/ask` pipeline gives feedback linked to the question ID. Track coverage per category.
42. Study plan for gaps, feeding the career planner and linking to LeetCode topics.
43. Kit UI: category tabs, evidence chips, practice flow, progress bar. Mount or delete `InterviewToolkitPanel` and the other orphaned project components.
    - **Gate:** the whole journey test passes with a stubbed LLM, from sources to a tailored resume and an interview kit.

## Stage H: Hardening and account basics (about 1.5 weeks)

44. Rate limiting: a strict limit on `/auth/*`; per-user limits on LLM endpoints; trusted-proxy handling for `X-Forwarded-For`; evict idle entries from the in-memory map.
45. Token lifetime: short-lived access token plus a refresh token in an httpOnly cookie.
46. Password reset and email verification through the chosen email provider, or a documented decision to restrict sign-in to Google. Without this, a forgotten password locks the user out.
47. Account deletion: `DELETE /account` removes all of a user's data (including stored files and encrypted tokens). Add data export if time allows.
48. Collapse the remaining parallel implementations, one at a time, each with tests first: one role-fit module, one resume-analysis entry point (decide whether `/resume/review` and `/resume/analyze` are separate features), one bullet-analysis path. Migrate the remaining `chat_completion` call sites to `llm_json`.
49. Dependency hygiene: declare `cryptography` directly, pin versions, replace `passlib`, fix the `utcnow()` deprecation. (`passlib` is already replaced: it had stopped working with the installed `bcrypt`, which broke email sign-up and sign-in.)
50. Remove the roughly 114 changelog-style comments ("FIX (Important #5)", "Phase 1 §1.4", "review finding #7") as part of touching each file, keeping comments that explain current behaviour.
51. Handle LLM prompt-injection risk: delimit untrusted text in the LinkedIn, job and resume prompts and add one test per prompt that injected instructions don't change the output schema.
    - **Gate:** an LLM outage never produces a 500, the rate-limit, deletion and password-reset tests pass.

## Stage I: Frontend quality (about 1–1.5 weeks)

52. Guided onboarding stepper: Connect sources → Review profile → Add a JD → Resume and Interview kit.
53. Resolve every remaining orphaned component (mount or delete). Add `knip` or an ESLint unused-exports check, plus ESLint and Prettier, to CI.
54. Consistent loading, empty, error and job-progress states, and a global error boundary.
55. Route-level code splitting. Target a main chunk under 300 kB.
56. Vitest and Testing Library tests for auth, the evidence page, the tailoring editor and the kit page. One Playwright test of the whole journey against staging.
57. Accessibility pass (labels, focus order, contrast in both themes) and mobile layout for the sidebar and dashboard.
    - **Gate:** a new user completes the journey without help, and lint, unused-code and Playwright checks are green in CI.

## Stage J: Deployment (about 1 week)

58. Production images: multi-stage frontend served by nginx; backend with no `--reload`, a non-root user, gunicorn with uvicorn workers.
59. Add the database service to `docker-compose.yml` for local use. Separate dev, staging and production configuration. CORS accepts a list of origins.
60. Managed Postgres with backups enabled, a restore tested once, and connection limits set. Run `alembic upgrade head` as a release step, with a written rollback note.
61. Secrets in the platform's secret store (`JWT_SECRET`, `ENCRYPTION_KEY`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, email provider key), a written rotation procedure, and no `.env` in any image. Note that changing `ENCRYPTION_KEY` invalidates stored GitHub tokens.
62. CI/CD: on merge to main, run tests, build images, deploy to staging and run the smoke test. Production deploys are manual with approval.
63. HTTPS and domain: TLS, HSTS, secure cookies; update Google OAuth origins.
64. Observability: request-ID middleware, JSON logs, error tracking (Sentry), an uptime check, `/health` plus a `/ready` that checks the database, and LLM spend and latency metrics.
65. Smoke-test script: register a user, upload a sample resume, add a JD, generate a resume and a kit, and exit non-zero on failure.
66. Privacy policy and terms, including that user data is sent to the LLM provider.
67. Rewrite `README.md` and `docs/development.md` to match reality: setup, environment variable table, architecture overview, testing, deployment and rollback.
    - **Gate:** `docker compose up` works from a fresh clone, staging deploys automatically and passes the smoke test, and a production deploy followed by a rollback has been rehearsed.

## Stage K: Beta and launch (1–2 weeks, partly elapsed time)

68. Dogfood: run the journey on your own profile with 3 real JDs and fix everything that is awkward.
69. Closed beta with 5–10 real users. Watch logs, errors and LLM cost per journey.
70. Tune prompts, limits and budgets from real data.
71. Launch checklist, all required:
    - the success criteria in the problem statement are met (journey under 15 minutes, zero unsupported claims, every bullet traced, journey test green in CI, graceful failure with the LLM down)
    - a backup restore has been tested
    - error alerts reach you
    - the account deletion flow works
    - a rollback has been rehearsed

## Gates in summary

| After step | Condition |
|---|---|
| 5 | CI green on a clean clone |
| 12 | Authorization matrix and JD steps of the journey test pass; a JD added in the UI appears in every picker |
| 20 | Repos create project candidates, no duplicates on re-sync, edits survive |
| 24 | Every "met" requirement links to evidence |
| 37 | Zero unflagged unsupported claims on the 10-pair test set |
| 43 | Full journey test passes with a stubbed LLM |
| 51 | LLM outage never causes a 500; rate-limit, deletion and password-reset tests pass |
| 57 | Playwright journey, lint and unused-code checks green |
| 67 | Fresh-clone compose works; staging deploys and passes smoke test; rollback rehearsed |

## Main risks

| Risk | Mitigation |
|---|---|
| LLM rewrites invent claims | Grounding gate and the zero-unsupported-claims test come first; flag or drop anything unverifiable |
| LLM cost or rate limits | Per-user budgets, caching, and a deterministic fallback for every feature |
| Merging confidence modules changes scores | Characterization tests before the merge (step 16) |
| Dropping tables or migrating JD rows loses data | Back up and review row counts before each destructive migration |
| Scope creep from secondary features | Frozen; touch only to unbreak or delete |
| Characters missing from the exported PDF | Bundle a font file and prove PDF export in the Docker image during step 36 |

## Explicitly deferred (not required for launch)

Non-engineering roles, job search or auto-apply, LinkedIn scraping, mobile apps, team or recruiter accounts, payments, live voice or video mock interviews, and any new work on dashboard nudges, the weekly brief, the career planner, or the Identity page analytics.
