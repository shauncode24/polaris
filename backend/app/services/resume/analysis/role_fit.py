# backend/app/services/resume/analysis/role_fit.py
import json
from app.core.llm import chat_completion, MODEL
from app.services.jobs.skill_categories import CATEGORY_MAP

ROLE_ARCHETYPES = {
    "Backend Engineer": {"Backend Development", "Database & Data"},
    "Frontend Engineer": {"Frontend Development"},
    "Full Stack Engineer": {"Backend Development", "Frontend Development"},
    "AI/ML Engineer": {"AI/ML Engineering"},
    "DevOps / Platform": {"Infrastructure & DevOps"},
}

def compute_role_fit(evidence_skills: list[dict]) -> list[dict]:
    covered_categories = set()
    for s in evidence_skills:
        if s.get("confidence") == "low":
            continue
        # Check canonical first, then fall back to name
        key = s.get("canonical") or s.get("name") or ""
        cat = CATEGORY_MAP.get(key.lower())
        if cat:
            covered_categories.add(cat)
            
    results = []
    for role, needed in ROLE_ARCHETYPES.items():
        overlap = len(needed & covered_categories)
        pct = round((overlap / len(needed)) * 100)
        results.append({"role": role, "match_pct": pct})
        
    return sorted(results, key=lambda r: r["match_pct"], reverse=True)

async def compute_role_fit_via_ai(raw_text: str) -> list[dict]:
    system_prompt = """You are a technical career matching AI. Analyze the candidate's resume text and evaluate their suitability for the following five roles:
1. Backend Engineer
2. Frontend Engineer
3. Full Stack Engineer
4. AI/ML Engineer
5. DevOps / Platform

For each role, output a match percentage from 0 to 100 based strictly on their experience, technologies, and projects mentioned in the text.
Output ONLY a valid JSON object matching this schema, no markdown, no prose:
{
  "roles": [
    {"role": "Backend Engineer", "match_pct": int},
    {"role": "Frontend Engineer", "match_pct": int},
    {"role": "Full Stack Engineer", "match_pct": int},
    {"role": "AI/ML Engineer", "match_pct": int},
    {"role": "DevOps / Platform", "match_pct": int}
  ]
}
"""
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        return parsed.get("roles", [])
    except Exception as e:
        print("AI role fit computation failed, falling back to deterministic:", e, flush=True)
        return []
