"""Goal-scoped curriculum knowledge base.

This is the fix for the core modeling flaw: skills are too coarse a unit
("FastAPI" isn't something you study, it's a bag of a dozen sub-topics),
and an unscoped skill list lets goal-irrelevant skills (JavaScript on an
ML goal) into the planning conversation at all.

This module does exactly ONE deterministic thing: given a goal title, it
narrows the universe down to the topics that are actually part of that
goal's curriculum. It does NOT rank those topics, decide which ones
matter most, or choose how to teach them — that's still entirely up to
the LLM. Think of this as scoping, not planning.

Deliberately small and hand-seeded, same philosophy as skill_categories.py
and github_taxonomy.py elsewhere in this codebase — cheap, extend by hand
as new goal phrasing shows up. "order" is a rough suggested-sequence hint
only (e.g. math before modeling before deployment) — the prompt tells the
LLM explicitly that this is a starting point it's free to reorder.
"""

# domain_key -> [(topic, order), ...]
DOMAIN_CURRICULA: dict[str, list[tuple[str, int]]] = {
    "machine_learning": [
        ("Linear Algebra & Probability Refresher", 1),
        ("Gradient Descent & Optimization Basics", 2),
        ("Linear & Logistic Regression", 3),
        ("Classification Metrics (Precision/Recall/ROC)", 4),
        ("Decision Trees & Random Forests", 5),
        ("Gradient Boosting (XGBoost/LightGBM)", 6),
        ("Feature Engineering", 7),
        ("Clustering & Dimensionality Reduction (PCA)", 8),
        ("Model Evaluation & Hyperparameter Tuning", 9),
        ("Neural Network Fundamentals", 10),
        ("CNNs for Vision", 11),
        ("RNNs / Sequence Models", 12),
        ("Transformers & Attention", 13),
        ("End-to-End Kaggle-style Project", 14),
    ],
    "dsa": [
        ("Arrays & Hashing", 1),
        ("Two Pointers & Sliding Window", 2),
        ("Prefix Sums & Binary Search", 3),
        ("Stacks & Queues", 4),
        ("Linked Lists", 5),
        ("Trees & BSTs", 6),
        ("DFS / BFS on Trees & Graphs", 7),
        ("Graphs: Union-Find & Topological Sort", 8),
        ("Dynamic Programming: 1D", 9),
        ("Dynamic Programming: 2D / Knapsack", 10),
        ("Greedy & Intervals", 11),
        ("Backtracking", 12),
        ("Heaps & Priority Queues", 13),
        ("Mock Interview / Timed Practice", 14),
    ],
    "ai_engineer": [
        ("Python for Production Services", 1),
        ("API Design (FastAPI/REST)", 2),
        ("LLM Fundamentals & Prompting", 3),
        ("Embeddings & Vector Search", 4),
        ("RAG Pipeline Design", 5),
        ("Agent Orchestration (LangGraph/LangChain)", 6),
        ("Caching & Latency (Redis)", 7),
        ("Containerization & Deployment (Docker)", 8),
        ("Evaluation & Observability for LLM apps", 9),
        ("End-to-End AI Feature Project", 10),
    ],
    "backend": [
        ("Language Fundamentals (Python/C#/etc.)", 1),
        ("REST API Design", 2),
        ("Authentication & Authorization", 3),
        ("Database Design & ORMs", 4),
        ("Caching Strategies", 5),
        ("Testing (Unit/Integration)", 6),
        ("Containerization (Docker)", 7),
        ("CI/CD Basics", 8),
        ("System Design Fundamentals", 9),
        ("End-to-End Service Project", 10),
    ],
    "frontend": [
        ("JavaScript/TypeScript Fundamentals", 1),
        ("Component Architecture (React/Vue)", 2),
        ("State Management", 3),
        ("Routing & Data Fetching", 4),
        ("Styling Systems", 5),
        ("Performance Optimization", 6),
        ("Accessibility Basics", 7),
        ("Testing (Component/E2E)", 8),
        ("End-to-End UI Project", 9),
    ],
    "devops": [
        ("Linux & Shell Fundamentals", 1),
        ("Docker & Containerization", 2),
        ("CI/CD Pipelines", 3),
        ("Kubernetes Basics", 4),
        ("Infrastructure as Code (Terraform)", 5),
        ("Monitoring & Observability", 6),
        ("Cloud Provider Fundamentals", 7),
    ],
    # Fallback when the goal doesn't match a known domain — generic,
    # still better than nothing, and small enough not to overwhelm.
    "general_swe": [
        ("Git & Version Control Habits", 1),
        ("Testing Fundamentals", 2),
        ("System Design Basics", 3),
        ("Resume-Ready Project Polish", 4),
        ("Mock Interview Practice", 5),
    ],
}

# goal keyword (substring, lowercased) -> domain_key. Order matters only
# in that the FIRST domain matched becomes primary; a goal can match
# more than one domain (e.g. "AI Engineer" pulls both ai_engineer and,
# lightly, backend), which is intentional — real roles blend domains.
GOAL_DOMAIN_KEYWORDS: dict[str, str] = {
    "machine learning": "machine_learning",
    "ml engineer": "machine_learning",
    "data scientist": "machine_learning",
    "well versed with ml": "machine_learning",
    "ai engineer": "ai_engineer",
    "llm engineer": "ai_engineer",
    "dsa": "dsa",
    "leetcode": "dsa",
    "coding interview": "dsa",
    "crack": "dsa",  # "crack Google SWE interviews" etc.
    "backend engineer": "backend",
    "backend developer": "backend",
    "frontend engineer": "frontend",
    "frontend developer": "frontend",
    "react developer": "frontend",
    "devops engineer": "devops",
    "sre": "devops",
    "full stack": "backend",  # backend curriculum first; frontend added below
}


def get_relevant_domains(goal_title: str) -> list[str]:
    lowered = goal_title.lower()
    matched: list[str] = []
    for keyword, domain in GOAL_DOMAIN_KEYWORDS.items():
        if keyword in lowered and domain not in matched:
            matched.append(domain)
    if "full stack" in lowered and "frontend" not in matched:
        matched.append("frontend")
    if not matched:
        matched.append("general_swe")
    return matched


def get_curriculum_topics(domains: list[str]) -> list[dict]:
    """Flat, ordered topic pool across all matched domains. 'order' is a
    same-domain sequencing hint only — topics from different domains
    aren't comparable by order and shouldn't be interleaved purely by
    number.
    """
    topics = []
    for domain in domains:
        for topic, order in DOMAIN_CURRICULA.get(domain, []):
            topics.append({"domain": domain, "topic": topic, "suggested_order": order})
    return topics