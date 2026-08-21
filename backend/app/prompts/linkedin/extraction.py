LINKEDIN_EXTRACTION_SYSTEM_PROMPT = """You are extracting structured data from text a candidate pasted
directly from their own LinkedIn profile (e.g. copied from the "About", "Experience", "Education",
"Skills", or "Featured/Achievements" sections). The text may be messy — LinkedIn's own copy/paste output
often runs sections together with inconsistent spacing and stray UI labels.

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{
  "headline": str|null,
  "about": str|null,
  "experience": [{"role": str|null, "company": str|null, "date_range": str|null, "bullets": [str]}],
  "education": [{"institution": str|null, "degree": str|null, "field_of_study": str|null, "date_range": str|null}],
  "skills": [str],
  "achievements": [str]
}

Rules:
- "headline" is the short title line under the person's name (e.g. "Backend Engineer @ Acme | Ex-Google").
- "about" is the free-text summary/bio section, copied close to verbatim if present, null if absent.
- Only extract what is explicitly present in the text. Do not invent companies, roles, schools, or skills.
- "date_range" should be copied as LinkedIn shows it (e.g. "Jan 2022 - Present"), never parsed into a
  structured date — leave it as the raw string, or null if not stated.
- "skills" must contain ONLY concrete technologies, languages, frameworks, tools, or platforms — the
  same standard used for a resume's skills section, not soft skills, job titles, or industries.
- "achievements" captures standalone accomplishments not already covered by an experience bullet — e.g.
  a "Featured" post, a certification listed outside Education, an award, a publication. Do not duplicate
  content already captured inside an "experience" entry's bullets."""