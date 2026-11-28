# Actions needed from you

Things I can't do or shouldn't decide for you. Ordered by when they matter. Tick them off as you go.

## Now

- [x] **Commit Phase 1 and Stage C.** Done.
- [x] **Commit step 21.** Done.
- [x] **Commit step 22.** Done.
- [x] **Commit step 23.** Done.
- [x] **Commit step 24.** Done.
- [x] **Commit step 25.** Done.
- [x] **Commit step 26.** Done.
- [x] **Commit the password fix.** Done. Run `uv sync` from `backend/` on any other machine that runs the app.
- [x] **Commit step 27.** Done.
- [x] **Commit step 28.** Done.
- [x] **Commit step 29.** Done.
- [x] **Commit step 30.** Done.
- [x] **Commit the resume date fix.** Done.
- [x] **Commit step 31.** Done.
- [x] **Commit step 32.** Done.
- [x] **Commit step 33.** Done.
- [x] **Commit step 34.** Done.
- [x] **Commit step 35.** Done, with the skill spelling and contact detail fixes.
- [x] **Commit step 36.** Done.
- [x] **Commit step 37.** Done.
- [ ] **Commit step 38.**
- [ ] **Open a downloaded resume in Microsoft Word and a PDF reader** and tell me what should look different. It is A4; say if you need US Letter. Run `uv sync` from `backend/` on any other machine first (ReportLab is new).
- [ ] **Try the Tailored Resume page** (after migrating): pick one of your jobs, generate, and accept, reject and edit a few lines. Tell me whether the confirmation warnings are too frequent with real suggestions, and what you miss being able to change (skills, job headings and removing a bullet aren't editable yet). Add your phone number and LinkedIn link under your name.
- [ ] **Try the AI features once the Groq allowance has reset:** upload a resume, add a job, open its Skill Gap page, generate a plan and ask an interview question. Most of these have not been run against the real model since step 25. If one shows a fallback or an "incomplete answer" message, send me the server's `llm label=...` log lines.
- [ ] **Back up the Neon database before migrating.** Use the Neon console (branch or snapshot). The migrations drop `job_descriptions` and the old tailoring cache and rewrite goals; the downgrade restores structure only, not data.
- [ ] **Apply the migrations to Neon.** From `backend/`: `uv run alembic upgrade head`. There are now thirteen new ones, applied in order: LinkedIn tables and `source` columns that the real database is currently missing (resume upload and LinkedIn need them), the job re-key, the unused-table drop, the evidence review columns, repo description/URL, the primary target flag, the background jobs table, the daily usage table, the tailored resumes table, the date wording columns, the contact detail columns, the tailoring cache drop and the interview kit tables (sign-in fails without the contact detail columns, and most AI features without the background jobs and daily usage tables). Expect the 2 legacy goals to lose their job link if their job can't be matched.
- [ ] **After migrating, re-sync GitHub once** (Profile page, GitHub card). Repo descriptions and URLs are only stored from the next sync on, and GitHub-only projects are only created by a sync or a resume upload.
- [ ] **Re-sync LeetCode once.** Solved problems only count toward "data structures" and "algorithms" from the next sync on.
- [ ] **Upload your resume again once** (this also saves its dates; then paste your LinkedIn text again if you use it). Evidence rows saved by earlier uploads can be attached to the wrong role (a bug fixed in step 21). A fresh upload replaces them: older rows stop counting.
- [ ] **Paste your saved jobs in again.** Jobs analysed before step 22 keep their old skill names, and some may be missing requirements because the model's reply was cut off. A re-added job appears as a new entry; delete the old one from the library on the Job & Company Intel page.
- [ ] **Try the job library in the browser** (after migrating): set a primary target, compare two jobs, delete one, then open Career Planner and Interview Prep and check both start from the primary target.
- [ ] **Open the Skill Gap page for one job** and check that each requirement expands to the right projects and bullets, and that the severity labels read sensibly. Expect some scores to differ from before: re-uploads no longer inflate them, and unsupported resume claims are now discounted here too.
- [ ] **Click through the My Profile page once** after migrating and syncing. I verified the backend with 212 automated tests and confirmed the frontend builds, but I have not seen the page in a browser: check that projects show their source badges, that Confirm / Edit / Hide / Restore work on a project, an experience and a skill, and that the LinkedIn panel imports. Tell me what looks wrong.
- [ ] **Decide what to do with `backend/app/scripts/clear_db.py`.** It truncates every table in whatever `DATABASE_URL` points at (currently Neon). I left it. Options: delete it, or make it refuse to run unless the database name contains `test`.
- [ ] **Remove the throwaway test database when you're done:** `docker rm -f polaris-test-pg`. Docker Desktop was started for it and is still running.

## Decisions I'm waiting on

- [ ] **Daily AI limit per user.** Set to 100 calls. On Groq's free tier that is too generous to protect anyone: one person using all of it could spend the whole app's 200,000 daily tokens. Roughly 30 would stop one user taking everything but still allows only about a handful of active users a day. Change it with `LLM_DAILY_CALLS_PER_USER` in `.env`; decide it together with the provider below.
- [ ] **How much evidence should count?** A skill needs a score of 60% to be met and 30% to count partly. One source rarely gets there: a skill used in one job (25%) or seen in one ordinary GitHub repo (18% to 39%) is usually shown as a gap, and one project that describes it (35%) only counts partly. LeetCode is more generous by design: 100 problems across 5 topics meets "algorithms" by itself. Tell me if either should change; the numbers are in `services/evidence/scoring.py`.
- [ ] **Hosting** (Render or Fly.io with managed Postgres, or one VPS). Needed for step 13 (staging) and Stage J.
- [ ] **Password reset and email verification.** The app has email/password sign-in and no reset flow, so a forgotten password locks the user out. Choose: build it (needs a transactional email provider such as Resend or Postmark), or drop email/password and keep Google sign-in only.
- [ ] **`services/projects/curation.py`.** Only tests use it, the app never calls it. Keep, wire in, or delete?
- [ ] **LLM provider and monthly budget.** Currently Groq (`openai/gpt-oss-120b`). The tailored-resume and interview-kit stages will make many more LLM calls per user: rewording one resume takes a call of about 750 tokens for each bullet that mentions a job skill, at most 32 calls (about 24,000 tokens). The free tier is too small to launch on: 200,000 tokens a day and 8,000 a minute for the whole app, where analysing one job takes about 6,000 to 7,000. That is roughly 30 jobs a day for all users together, and a very long posting may not fit in the per-minute limit at all. One interview answer takes three calls, roughly 6,000 tokens, so about one a minute and 30 a day.

## Things only you can do

- [ ] **Optional: add job descriptions you care about** (for example campus placement ones) as `.txt` files in `backend/eval/jd_extraction/jds/`, list the skills you expect in `gold.json` beside it, and ask me to run the check. It needs a local database; the command is at the top of `app/scripts/eval_jd_extraction.py`.
- [ ] **Run the journey once by hand with a real `GROQ_API_KEY`** (Stage A, steps 3 and 4, which you skipped): register, upload a resume, sync GitHub, add a job, skill gap, tailoring, interview. Write what breaks into `docs/known-issues.md`. Only job analysis and parts of interview practice have been checked against the real model.
- [ ] **Repair CI** (Stage A, step 5, skipped): the workflow still runs on Windows with no Postgres, so the database-backed tests are skipped there. I can do this edit if you tell me to.
- [ ] **Staging account and secrets** for the hosting choice above: `JWT_SECRET`, `ENCRYPTION_KEY`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`. Never paste them into chat.
- [ ] **Google OAuth console:** add the staging and production origins to the allowed origins.

## Later (not yet needed)

- [ ] Privacy policy and terms (they must say user data is sent to the LLM provider).
- [ ] Domain name and TLS, once hosting is chosen.
- [ ] 5 to 10 real people for the closed beta (Stage K).
- [ ] Error-tracking account (Sentry or similar) for Stage J.
