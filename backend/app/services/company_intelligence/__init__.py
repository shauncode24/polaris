# backend/app/services/company_intelligence/__init__.py
# app/services/company_intelligence package — see design doc revision,
# "Company Intelligence Should Remain Independent". Deliberately thin
# right now: population happens inside job_intelligence/builder.py's ONE
# extraction call; this module only owns reads, so future enrichment
# sources (recruiter notes, interview experiences) can add their own
# write paths here without touching Job Intelligence.