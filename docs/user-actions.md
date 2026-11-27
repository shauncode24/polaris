# Actions needed from you

Things I can't do or shouldn't decide for you. Ordered by when they matter. Tick them off as you go.

## Now

- [x] **Commit Phase 1 and Stage C.** Done.
- [x] **Commit step 21.** Done.
- [x] **Commit step 22.** Done.
- [ ] **Commit step 23.**
- [ ] **Back up the Neon database before migrating.** Use the Neon console (branch or snapshot). The migrations drop `job_descriptions` and rewrite goals and the tailoring cache; the downgrade restores structure only, not data.
- [ ] **Apply the migrations to Neon.** From `backend/`: `uv run alembic upgrade head`. There are now six new ones, applied in order: LinkedIn tables and `source` columns that the real database is currently missing (resume upload and LinkedIn need them), the job re-key, the unused-table drop, the evidence review columns, repo description/URL, and the primary target flag. Expect the 2 legacy goals to lose their job link if their job can't be matched.
- [ ] **After migrating, re-sync GitHub once** (Profile page, GitHub card). Repo descriptions and URLs are only stored from the next sync on, and GitHub-only projects are only created by a sync or a resume upload.
- [ ] **Upload your resume again once.** Evidence rows saved by earlier uploads can be attached to the wrong role (a bug fixed in step 21). A fresh upload replaces them: older rows stop counting.
- [ ] **Paste your saved jobs in again.** Jobs analysed before step 22 keep their old skill names, and some may be missing requirements because the model's reply was cut off. A re-added job appears as a new entry; delete the old one from the library on the Job & Company Intel page.
- [ ] **Try the job library in the browser** (after migrating): set a primary target, compare two jobs, delete one, then open Career Planner and Interview Prep and check both start from the primary target.
- [ ] **Open the Skill Gap page for one job** and check that each requirement expands to the right projects and bullets, and that the severity labels read sensibly. Expect some scores to differ from before: re-uploads no longer inflate them, and unsupported resume claims are now discounted here too.
- [ ] **Click through the My Profile page once** after migrating and syncing. I verified the backend with 212 automated tests and confirmed the frontend builds, but I have not seen the page in a browser: check that projects show their source badges, that Confirm / Edit / Hide / Restore work on a project, an experience and a skill, and that the LinkedIn panel imports. Tell me what looks wrong.
- [ ] **Decide what to do with `backend/app/scripts/clear_db.py`.** It truncates every table in whatever `DATABASE_URL` points at (currently Neon). I left it. Options: delete it, or make it refuse to run unless the database name contains `test`.
- [ ] **Remove the throwaway test database when you're done:** `docker rm -f polaris-test-pg`. Docker Desktop was started for it and is still running.

## Decisions I'm waiting on

- [ ] **Hosting** (Render or Fly.io with managed Postgres, or one VPS). Needed for step 13 (staging) and Stage J.
- [ ] **Password reset and email verification.** The app has email/password sign-in and no reset flow, so a forgotten password locks the user out. Choose: build it (needs a transactional email provider such as Resend or Postmark), or drop email/password and keep Google sign-in only.
- [ ] **`services/projects/curation.py`.** Only tests use it, the app never calls it. Keep, wire in, or delete?
- [ ] **LLM provider and monthly budget.** Currently Groq (`openai/gpt-oss-120b`). The tailored-resume and interview-kit stages will make many more LLM calls per user. The free tier is too small to launch on: 200,000 tokens a day and 8,000 a minute for the whole app, where analysing one job takes about 6,000 to 7,000. That is roughly 30 jobs a day for all users together, and a very long posting may not fit in the per-minute limit at all.

## Things only you can do

- [ ] **Optional: add job descriptions you care about** (for example campus placement ones) as `.txt` files in `backend/eval/jd_extraction/jds/`, list the skills you expect in `gold.json` beside it, and ask me to run the check. It needs a local database; the command is at the top of `app/scripts/eval_jd_extraction.py`.
- [ ] **Run the journey once by hand with a real `GROQ_API_KEY`** (Stage A, steps 3 and 4, which you skipped): register, upload a resume, sync GitHub, add a job, skill gap, tailoring, interview. Write what breaks into `docs/known-issues.md`. Everything I've verified so far used a stubbed or absent LLM, so real-model behaviour is untested.
- [ ] **Repair CI** (Stage A, step 5, skipped): the workflow still runs on Windows with no Postgres, so the 32 database-backed tests are skipped there. I can do this edit if you tell me to.
- [ ] **Staging account and secrets** for the hosting choice above: `JWT_SECRET`, `ENCRYPTION_KEY`, `GROQ_API_KEY`, `GOOGLE_CLIENT_ID`. Never paste them into chat.
- [ ] **Google OAuth console:** add the staging and production origins to the allowed origins.

## Later (not yet needed)

- [ ] Privacy policy and terms (they must say user data is sent to the LLM provider).
- [ ] Domain name and TLS, once hosting is chosen.
- [ ] 5 to 10 real people for the closed beta (Stage K).
- [ ] Error-tracking account (Sentry or similar) for Stage J.
