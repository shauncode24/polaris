"""Best-effort, ADVISORY coverage check: for each curriculum topic (already
scoped to the goal's relevant domain(s) by curriculum.py), does the user
appear to have any real evidence touching it? This is intentionally loose
— a rough signal for the LLM to reason over, not an authoritative judgment.
Nothing downstream trusts this as ground truth or uses it to filter what
the LLM is allowed to write about.

Evidence priority order per topic:
  1. Resume/evidence skills (skills_by_confidence)
  2. LeetCode topic mastery
  3. GitHub technology depth map (technology_depth from github sync insights)
     — a score >=30 counts as partial, >=60 as strong. This is the weakest
     signal (breadth proxy, not a direct skill confirmation) but is better
     than reporting "no evidence" when the user has multiple repos using
     the relevant technology.
"""

# topic name -> substrings to look for in the user's canonical skill
# names / leetcode canonical topic names / evidence source labels.
# Loose and hand-seeded on purpose — false negatives just mean the LLM
# sees "no evidence found," which is a safe default, not a hard block.
TOPIC_EVIDENCE_ALIASES: dict[str, list[str]] = {
    "Arrays & Hashing": ["arrays & hashing"],
    "Two Pointers & Sliding Window": ["sliding window"],
    "Prefix Sums & Binary Search": ["binary search"],
    "Stacks & Queues": ["stack", "queue"],
    "Linked Lists": ["linked list"],
    "Trees & BSTs": ["trees"],
    "DFS / BFS on Trees & Graphs": ["graphs"],
    "Graphs: Union-Find & Topological Sort": ["graphs"],
    "Dynamic Programming: 1D": ["dynamic programming"],
    "Dynamic Programming: 2D / Knapsack": ["dynamic programming"],
    "Greedy & Intervals": ["greedy", "intervals"],
    "Backtracking": ["backtracking"],
    "Heaps & Priority Queues": ["heap"],
    "API Design (FastAPI/REST)": ["fastapi", "rest_api", "django", "flask", "express"],
    "Authentication & Authorization": ["jwt", "oauth", "aspnet_core"],
    "Database Design & ORMs": ["postgres", "sql_server", "mongodb", "ef_core"],
    "Caching Strategies": ["redis"],
    "Caching & Latency (Redis)": ["redis"],
    "Testing (Unit/Integration)": ["testing", "pytest"],
    "Containerization (Docker)": ["docker"],
    "Containerization & Deployment (Docker)": ["docker"],
    "CI/CD Basics": ["ci/cd", "cicd"],
    "CI/CD Pipelines": ["ci/cd", "cicd"],
    "Kubernetes Basics": ["kubernetes"],
    "Infrastructure as Code (Terraform)": ["terraform"],
    "Component Architecture (React/Vue)": ["react", "vue", "angular"],
    "JavaScript/TypeScript Fundamentals": ["javascript", "typescript"],
    "LLM Fundamentals & Prompting": ["openai", "langchain", "langgraph"],
    "Embeddings & Vector Search": ["vector_search", "rag"],
    "RAG Pipeline Design": ["rag"],
    "Agent Orchestration (LangGraph/LangChain)": ["langgraph", "langchain"],
    "Language Fundamentals (Python/C#/etc.)": ["python", "csharp"],
}


def _coverage_for_topic(
    topic: str,
    skills_by_confidence: list[dict],
    leetcode_topic_mastery: list[dict],
    technology_depth: dict[str, dict] | None = None,
) -> dict:
    aliases = TOPIC_EVIDENCE_ALIASES.get(topic, [])
    if not aliases:
        return {"coverage": "unknown", "confidence": None, "reasons": ["no evidence-mapping rule for this topic yet"]}

    for entry in skills_by_confidence:
        if entry["skill"] in aliases:
            confidence = entry["confidence"]
            label = "strong" if confidence >= 0.75 else ("partial" if confidence >= 0.3 else "weak")
            return {
                "coverage": label,
                "confidence": confidence,
                "reasons": [f"related skill '{entry['skill']}' at confidence {confidence:.2f}"],
            }

    for lc in leetcode_topic_mastery:
        if lc["topic"].lower() in [a.lower() for a in aliases] or any(a in lc["topic"].lower() for a in aliases):
            mastery = lc["mastery"]
            label = "strong" if mastery in ("Consistent Practice", "Extensive Practice") else (
                "partial" if mastery in ("Some Practice", "Introduced") else "weak"
            )
            return {
                "coverage": label,
                "confidence": None,
                "reasons": [f"LeetCode mastery for '{lc['topic']}': {mastery} ({lc['problems']} solved)"],
            }

    # 3rd-priority: GitHub technology depth map — weakest signal (breadth,
    # not direct skill confirmation) but better than reporting "no evidence"
    # when the user has real repos using the relevant technology.
    if technology_depth:
        for alias in aliases:
            # technology_depth keys are the exact technology names from github
            # (e.g. "FastAPI", "React") — case-sensitive. Try both forms.
            for key in (alias, alias.title(), alias.upper()):
                depth_entry = technology_depth.get(key)
                if depth_entry and isinstance(depth_entry, dict):
                    score = depth_entry.get("score", 0)
                    label_str = depth_entry.get("label", "")
                    if score >= 60:
                        return {
                            "coverage": "strong",
                            "confidence": None,
                            "reasons": [f"GitHub depth signal: '{key}' at {score}/100 ({label_str})"],
                        }
                    if score >= 30:
                        return {
                            "coverage": "partial",
                            "confidence": None,
                            "reasons": [f"GitHub depth signal: '{key}' at {score}/100 ({label_str})"],
                        }

    return {"coverage": "none", "confidence": None, "reasons": ["no evidence found in your profile for this topic"]}


def build_topic_signals(
    curriculum_topics: list[dict],   # [{"domain", "topic", "suggested_order"}, ...]
    skills_by_confidence: list[dict],
    leetcode_topic_mastery: list[dict],
    jd_missing_skills: set[str],
    ats_missing_keywords: set[str],
    technology_depth: dict[str, dict] | None = None,
    leetcode_plan_adherence: list[dict] | None = None,
) -> list[dict]:
    # Index by canonical LeetCode topic name for O(1) lookup below. Entries
    # come straight from leetcode_insights.build_plan_adherence — real,
    # already-computed facts (status "followed"/"not_yet_followed", the
    # date recommended, and how many new problems were solved since).
    adherence_by_topic = {a["topic"]: a for a in (leetcode_plan_adherence or [])}

    signals = []
    for entry in curriculum_topics:
        topic = entry["topic"]
        coverage_info = _coverage_for_topic(
            topic, skills_by_confidence, leetcode_topic_mastery, technology_depth
        )

        extra_reasons = []
        aliases = TOPIC_EVIDENCE_ALIASES.get(topic, [])
        if any(a in jd_missing_skills for a in aliases):
            extra_reasons.append("related skill flagged missing in your most recent Skill Gap Analysis")
        if any(a in ats_missing_keywords for a in aliases):
            extra_reasons.append("related keyword flagged missing on your resume's ATS review")

        # Cross-reference against the LeetCode AI Coach's own prior
        # recommendation for this exact canonical topic, if one exists —
        # curriculum "topic" strings don't share vocabulary with LeetCode's
        # canonical topic names 1:1, so this only fires on an exact match
        # (a real, if imperfect, signal is better than a fuzzy false one).
        adherence = adherence_by_topic.get(topic)
        if adherence is not None:
            if adherence["status"] == "not_yet_followed":
                extra_reasons.append(
                    f"the LeetCode AI Coach recommended focusing on {topic} on "
                    f"{adherence['recommended_at'][:10]} and no new problems have been solved here since"
                )
            else:
                extra_reasons.append(
                    f"you've already been acting on the LeetCode AI Coach's recommendation to focus on "
                    f"{topic} ({adherence['new_problems_since_recommendation']} new problems solved since)"
                )

        signals.append({
            "domain": entry["domain"],
            "topic": topic,
            "suggested_order": entry["suggested_order"],
            "coverage": coverage_info["coverage"],
            "confidence": coverage_info["confidence"],
            "reasons": coverage_info["reasons"] + extra_reasons,
        })

    return signals