"""Best-effort, ADVISORY coverage check: for each curriculum topic (already
scoped to the goal's relevant domain(s) by curriculum.py), does the user
appear to have any real evidence touching it? This is intentionally loose
— a rough signal for the LLM to reason over, not an authoritative judgment.
Nothing downstream trusts this as ground truth or uses it to filter what
the LLM is allowed to write about.
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

    return {"coverage": "none", "confidence": None, "reasons": ["no evidence found in your profile for this topic"]}


def build_topic_signals(
    curriculum_topics: list[dict],   # [{"domain", "topic", "suggested_order"}, ...]
    skills_by_confidence: list[dict],
    leetcode_topic_mastery: list[dict],
    jd_missing_skills: set[str],
    ats_missing_keywords: set[str],
) -> list[dict]:
    signals = []
    for entry in curriculum_topics:
        topic = entry["topic"]
        coverage_info = _coverage_for_topic(topic, skills_by_confidence, leetcode_topic_mastery)

        extra_reasons = []
        aliases = TOPIC_EVIDENCE_ALIASES.get(topic, [])
        if any(a in jd_missing_skills for a in aliases):
            extra_reasons.append("related skill flagged missing in your most recent Skill Gap Analysis")
        if any(a in ats_missing_keywords for a in aliases):
            extra_reasons.append("related keyword flagged missing on your resume's ATS review")

        signals.append({
            "domain": entry["domain"],
            "topic": topic,
            "suggested_order": entry["suggested_order"],
            "coverage": coverage_info["coverage"],
            "confidence": coverage_info["confidence"],
            "reasons": coverage_info["reasons"] + extra_reasons,
        })

    # Ordered by domain-appearance then suggested_order — preserves a
    # sensible default curriculum sequence. This is a STARTING POINT the
    # prompt explicitly tells the LLM it can reorder based on coverage
    # and days available, not a schedule it has to follow.
    return signals