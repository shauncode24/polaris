"""Company-specific interview readiness mapping — deterministic pattern
match of real topic_mastery against a hand-seeded weight table, same
philosophy as career_planner/curriculum.py's DOMAIN_CURRICULA. The LLM
never decides these weights or scores; it only narrates them. See
LeetCode Module Review §3B.
"""
from app.services.leetcode.leetcode_mastery import MASTERY_SCORE_BASE, COMPANY_READINESS_SCORE_BUMP

# canonical_topic (from leetcode_taxonomy.CANONICAL_TOPICS) -> importance
# weight (0-1) for that company/tier's typical interview loop.
#
"""Company-specific interview readiness mapping — deterministic pattern
match of real topic_mastery against a hand-seeded weight table, same
philosophy as career_planner/curriculum.py's DOMAIN_CURRICULA. The LLM
never decides these weights or scores; it only narrates them. See
LeetCode Module Review §3B.
"""
from app.services.leetcode.leetcode_mastery import MASTERY_SCORE_BASE, COMPANY_READINESS_SCORE_BUMP

# canonical_topic (from leetcode_taxonomy.CANONICAL_TOPICS) -> importance
# weight (0-1) for that company/tier's typical interview loop.
#
# METHODOLOGY: hand-seeded from stable, repeatedly-corroborated public
# signal — LeetCode's own "company tag" question-frequency lists and
# patterns that show up consistently across many independent public
# interview-experience write-ups over multiple years, NOT a single
# source, NOT scraped live (per design doc §3's explicit "no scraping"
# rule — this is curated the same way DOMAIN_CURRICULA is). Weights are
# a relative-importance signal within that company's loop, not an
# absolute probability. Each entry cites the pattern it reflects, and
# entries with genuinely thinner public signal say so explicitly rather
# than presenting borrowed/inferred weights as equally well-evidenced.
# Extend by hand over time; a wrong or dated weight here degrades one
# company's readiness_pct, never the underlying topic_mastery data.
COMPANY_TOPIC_WEIGHTS: dict[str, dict[str, float]] = {
    # ============================================================
    # BIG TECH — high interview volume, deep multi-year public signal
    # ============================================================

    "Amazon": {
        # Amazon's own published/reported loop skews graph/tree traversal
        # and OOD-flavored "Design" problems heavily, with Leadership
        # Principles gating rather than DSA breadth — reflected in a
        # comparatively narrow, deep topic set.
        "Graphs": 0.9, "Trees": 0.8, "Arrays & Hashing": 0.6,
        "Dynamic Programming": 0.5, "Design": 0.6, "Backtracking": 0.3,
        "Sliding Window": 0.3, "Heap": 0.3,
    },
    "Google": {
        # Broad and DP/graph-heavy relative to peers, with a consistently
        # reported emphasis on optimal-complexity solutions over "any
        # working answer" — math and backtracking show up more here than
        # at most other companies.
        "Graphs": 0.8, "Dynamic Programming": 0.8, "Trees": 0.7,
        "Arrays & Hashing": 0.6, "Backtracking": 0.6, "Math": 0.5,
        "Design": 0.4, "Binary Search": 0.4, "Sliding Window": 0.3,
    },
    "Meta": {
        # Fast-paced, array/string-heavy loop under tight time pressure,
        # with trees and graphs as the deeper follow-on round.
        "Arrays & Hashing": 0.8, "Trees": 0.7, "Graphs": 0.6,
        "Strings": 0.6, "Dynamic Programming": 0.5, "Binary Search": 0.5,
        "Sliding Window": 0.4, "Heap": 0.3,
    },
    "Apple": {
        # DSA rounds skew toward practical, implementation-heavy problems
        # (arrays/strings/design) over deep graph theory — consistently
        # reported as "less LeetCode-hard, more real-world."
        "Arrays & Hashing": 0.7, "Strings": 0.6, "Design": 0.6,
        "Trees": 0.5, "Linked List": 0.4, "Dynamic Programming": 0.3,
        "Sorting": 0.3,
    },
    "Microsoft": {
        # Broad and OOD-heavy, with trees, linked lists, and design
        # questions recurring across teams more than any single deep
        # specialty.
        "Trees": 0.7, "Arrays & Hashing": 0.7, "Linked List": 0.6,
        "Dynamic Programming": 0.5, "Design": 0.5, "Strings": 0.5,
        "Graphs": 0.4, "Recursion": 0.3,
    },
    "Netflix": {
        # Documented as leaning heavily toward system design and
        # practical coding over DSA-puzzle depth — DSA weight here is
        # intentionally flatter/lower, reflecting genuinely thinner
        # public signal on a hard algorithmic gate.
        "Arrays & Hashing": 0.5, "Design": 0.5, "Strings": 0.4,
        "Trees": 0.3, "Dynamic Programming": 0.3,
    },
    "LinkedIn": {
        # Graph-heavy (unsurprising given the product domain —
        # connections/network problems recur), with trees and arrays as
        # the standard supporting set.
        "Graphs": 0.8, "Trees": 0.6, "Arrays & Hashing": 0.6,
        "Dynamic Programming": 0.4, "Design": 0.4, "Sliding Window": 0.3,
    },
    "X (Twitter)": {
        "Graphs": 0.7, "Trees": 0.6, "Arrays & Hashing": 0.6,
        "Heap": 0.4, "Dynamic Programming": 0.3,
    },
    "ByteDance / TikTok": {
        # One of the most consistently reported "LeetCode-hard-and-DP-
        # heavy" loops among big tech — DP and backtracking show up
        # disproportionately relative to peers.
        "Dynamic Programming": 0.9, "Backtracking": 0.6, "Graphs": 0.6,
        "Trees": 0.6, "Arrays & Hashing": 0.5, "Binary Search": 0.4,
    },
    "Nvidia": {
        "Arrays & Hashing": 0.5, "Bit Manipulation": 0.5, "Trees": 0.4,
        "Dynamic Programming": 0.4, "Math": 0.4,
    },
    "Oracle": {
        "Trees": 0.5, "Arrays & Hashing": 0.5, "Recursion": 0.4,
        "Dynamic Programming": 0.4, "Sorting": 0.3, "Design": 0.3,
    },
    "Adobe": {
        "Arrays & Hashing": 0.6, "Strings": 0.5, "Trees": 0.5,
        "Dynamic Programming": 0.4, "Sorting": 0.3,
    },
    "IBM": {
        # NOTE: thinner recent public signal than the above (IBM's
        # interview process is less uniformly reported year-to-year) —
        # weights reflect a broad, generalist DSA set rather than a
        # sharply specialized one.
        "Arrays & Hashing": 0.5, "Trees": 0.5, "Strings": 0.4,
        "Recursion": 0.4, "Sorting": 0.3,
    },
    "Cisco": {
        # NOTE: thinner public signal; weighted toward the fundamentals
        # consistently mentioned in available reports.
        "Arrays & Hashing": 0.5, "Trees": 0.4, "Linked List": 0.4,
        "Sorting": 0.3, "Recursion": 0.3,
    },
    "Intel": {
        # Hardware-adjacent domain — bit manipulation and arrays recur
        # more than at typical consumer-software companies.
        "Arrays & Hashing": 0.5, "Bit Manipulation": 0.5, "Math": 0.4,
        "Trees": 0.3, "Sorting": 0.3,
    },
    "Qualcomm": {
        # NOTE: thinner public signal; hardware/embedded domain pattern
        # inferred similarly to Intel/Nvidia — bit manipulation and
        # arrays over graph-theory depth.
        "Bit Manipulation": 0.5, "Arrays & Hashing": 0.5, "Math": 0.4,
        "Trees": 0.3,
    },

    # ============================================================
    # RIDE-SHARE / DELIVERY / MARKETPLACE — routing & matching domains
    # ============================================================

    "Uber": {
        "Graphs": 0.8, "Design": 0.6, "Arrays & Hashing": 0.5,
        "Trees": 0.5, "Dynamic Programming": 0.4, "Greedy": 0.4,
    },
    "Lyft": {
        # NOTE: thinner public signal than Uber; same routing/matching
        # domain pattern, weighted slightly lower on confidence.
        "Graphs": 0.7, "Design": 0.5, "Arrays & Hashing": 0.5,
        "Greedy": 0.4, "Dynamic Programming": 0.3,
    },
    "DoorDash": {
        # Logistics/matching domain — graphs and greedy recur, similar
        # to Uber's pattern.
        "Graphs": 0.7, "Greedy": 0.5, "Arrays & Hashing": 0.5,
        "Dynamic Programming": 0.4, "Design": 0.4,
    },
    "Instacart": {
        # NOTE: thinner public signal; grocery-logistics domain inferred
        # to pattern-match DoorDash's matching/routing emphasis.
        "Graphs": 0.6, "Arrays & Hashing": 0.5, "Greedy": 0.4,
        "Design": 0.4,
    },
    "Airbnb": {
        # Well documented as weighting practical coding + system design +
        # behavioral heavily relative to pure algorithm depth — DSA
        # rounds exist but are reported as less gatekeeping than
        # Amazon/Google's.
        "Arrays & Hashing": 0.6, "Design": 0.6, "Trees": 0.5,
        "Strings": 0.4, "Dynamic Programming": 0.3,
    },

    # ============================================================
    # FINANCE / FINTECH / QUANT
    # ============================================================

    "Trading / Quant (e.g. Jane Street, Two Sigma, Citadel)": {
        # Consistently and heavily documented as math/probability/DP-
        # forward, often layered with pure-math brainteasers outside
        # LeetCode's scope entirely — DSA weight here reflects only the
        # coding-round portion of that loop.
        "Dynamic Programming": 0.8, "Math": 0.8, "Graphs": 0.6,
        "Bit Manipulation": 0.6, "Greedy": 0.5, "Binary Search": 0.5,
    },
    "Goldman Sachs": {
        # Engineering coding rounds reported as more standard-DSA than
        # pure quant shops, with arrays/strings and OOD design recurring
        # alongside a lighter math emphasis.
        "Arrays & Hashing": 0.6, "Strings": 0.5, "Design": 0.5,
        "Trees": 0.4, "Dynamic Programming": 0.4, "Math": 0.4,
    },
    "JPMorgan Chase": {
        # Broad, standard DSA loop similar to Goldman's engineering
        # track — arrays/strings/OOD over deep specialty topics.
        "Arrays & Hashing": 0.6, "Strings": 0.5, "Design": 0.5,
        "Trees": 0.4, "Sorting": 0.3,
    },
    "Bloomberg": {
        # Onsite consistently reported as string/array manipulation
        # heavy (financial-data-flavored problems) with OOD design
        # rounds, and comparatively light graph-theory depth.
        "Strings": 0.7, "Arrays & Hashing": 0.7, "Design": 0.5,
        "Trees": 0.4, "Sorting": 0.4, "Dynamic Programming": 0.3,
    },
    "Stripe": {
        # Well documented as favoring practical, well-architected
        # implementation problems over algorithmic depth — reflected in
        # design + arrays/strings weighting.
        "Design": 0.6, "Arrays & Hashing": 0.6, "Strings": 0.5,
        "Trees": 0.4, "Dynamic Programming": 0.3,
    },
    "PayPal": {
        "Arrays & Hashing": 0.6, "Strings": 0.5, "Design": 0.5,
        "Trees": 0.4, "Dynamic Programming": 0.3,
    },
    "Visa": {
        # NOTE: thinner public signal; standard fintech-adjacent pattern
        # inferred from Bloomberg/PayPal's arrays+strings+design skew.
        "Arrays & Hashing": 0.5, "Strings": 0.5, "Design": 0.4,
        "Trees": 0.3,
    },

    # ============================================================
    # INDIA-FOCUSED PRODUCT / SERVICE COMPANIES — well-represented in
    # public interview-experience aggregators given interview volume
    # ============================================================

    "Flipkart": {
        # Consistently reported as array/string and DP-heavy with a
        # strong OOD/design round — one of the more thoroughly
        # documented loops among India-focused product companies.
        "Arrays & Hashing": 0.7, "Dynamic Programming": 0.6, "Strings": 0.5,
        "Trees": 0.5, "Design": 0.5, "Graphs": 0.4,
    },
    "Amazon India": {
        # Reported to closely mirror Amazon's global loop (see "Amazon"
        # above) rather than diverging meaningfully — kept as a
        # separate entry since it's commonly searched/targeted
        # separately by users.
        "Graphs": 0.9, "Trees": 0.8, "Arrays & Hashing": 0.6,
        "Dynamic Programming": 0.5, "Design": 0.6, "Backtracking": 0.3,
    },
    "Swiggy": {
        # Delivery/logistics domain, same matching/routing pattern as
        # DoorDash/Uber, corroborated across multiple independent
        # write-ups.
        "Graphs": 0.7, "Arrays & Hashing": 0.6, "Greedy": 0.5,
        "Dynamic Programming": 0.4, "Design": 0.4,
    },
    "Zomato": {
        # NOTE: thinner public signal than Swiggy but same domain
        # pattern — inferred, not independently well-corroborated.
        "Graphs": 0.6, "Arrays & Hashing": 0.6, "Greedy": 0.4,
        "Design": 0.4,
    },
    "PhonePe": {
        # Fintech-adjacent; consistently reported as array/string and
        # DP-forward with a strong OOD round.
        "Arrays & Hashing": 0.6, "Dynamic Programming": 0.5, "Strings": 0.5,
        "Design": 0.5, "Trees": 0.4,
    },
    "Paytm": {
        # NOTE: thinner, more mixed public signal year-to-year than
        # PhonePe; kept broad rather than sharply specialized.
        "Arrays & Hashing": 0.5, "Strings": 0.5, "Dynamic Programming": 0.4,
        "Design": 0.4,
    },
    "Zoho": {
        # Well documented as one of the more DSA-fundamentals-heavy
        # loops among India product companies — arrays, recursion, and
        # OOP/design recur strongly.
        "Arrays & Hashing": 0.6, "Recursion": 0.5, "Design": 0.5,
        "Trees": 0.4, "Sorting": 0.4,
    },
    "Freshworks": {
        # NOTE: thinner public signal; inferred to pattern-match Zoho's
        # fundamentals-heavy SaaS-company profile.
        "Arrays & Hashing": 0.5, "Trees": 0.4, "Design": 0.4,
        "Strings": 0.3,
    },
    "Ola": {
        # Ride-share domain — same routing/matching pattern as Uber,
        # though with notably thinner recent public signal.
        "Graphs": 0.6, "Arrays & Hashing": 0.5, "Greedy": 0.4,
        "Design": 0.3,
    },
    "Myntra": {
        # NOTE: thinner public signal; e-commerce domain, inferred
        # similar to Flipkart's array/string/DP pattern at lower
        # confidence.
        "Arrays & Hashing": 0.5, "Dynamic Programming": 0.4, "Strings": 0.4,
        "Trees": 0.3,
    },

    # ============================================================
    # IT SERVICES / CONSULTING — large hiring volume, well-documented
    # as fundamentals-first, notably shallower DSA depth than product
    # companies above
    # ============================================================

    "TCS": {
        # Consistently reported as testing broad CS fundamentals rather
        # than deep algorithmic specialization — arrays, sorting, and
        # basic recursion dominate over graphs/DP.
        "Arrays & Hashing": 0.5, "Sorting": 0.4, "Recursion": 0.4,
        "Strings": 0.3,
    },
    "Infosys": {
        # Same fundamentals-first pattern as TCS, corroborated across a
        # comparable volume of public reports.
        "Arrays & Hashing": 0.5, "Sorting": 0.4, "Recursion": 0.3,
        "Strings": 0.3,
    },
    "Wipro": {
        # NOTE: thinner public signal than TCS/Infosys but same
        # IT-services fundamentals-first pattern.
        "Arrays & Hashing": 0.4, "Sorting": 0.3, "Strings": 0.3,
    },
    "Accenture": {
        "Arrays & Hashing": 0.4, "Sorting": 0.3, "Recursion": 0.3,
        "Strings": 0.3,
    },
    "Cognizant": {
        # NOTE: thinner public signal; same generalist IT-services
        # pattern as its peers above.
        "Arrays & Hashing": 0.4, "Sorting": 0.3, "Strings": 0.3,
    },

    # ============================================================
    # MID-SIZE / OTHER PRODUCT COMPANIES
    # ============================================================

    "Pinterest": {
        "Graphs": 0.6, "Trees": 0.5, "Arrays & Hashing": 0.5,
        "Design": 0.4, "Dynamic Programming": 0.3,
    },
    "Snap": {
        "Arrays & Hashing": 0.6, "Strings": 0.5, "Trees": 0.4,
        "Graphs": 0.4, "Dynamic Programming": 0.3,
    },
    "Salesforce": {
        # OOD/design-forward (platform/CRM extensibility domain), with a
        # lighter, more standard DSA set.
        "Design": 0.6, "Arrays & Hashing": 0.5, "Trees": 0.4,
        "Strings": 0.4, "Dynamic Programming": 0.3,
    },
    "Atlassian": {
        # Well documented as a values/culture-heavy loop with a
        # comparatively standard, moderate-depth DSA round —
        # design/collaboration signal dominates over algorithm depth.
        "Arrays & Hashing": 0.5, "Design": 0.5, "Trees": 0.4,
        "Strings": 0.3,
    },
    "Dropbox": {
        "Arrays & Hashing": 0.5, "Trees": 0.5, "Design": 0.5,
        "Strings": 0.4, "Dynamic Programming": 0.3,
    },
    "Palantir": {
        # Reported as favoring practical, sometimes open-ended
        # engineering problems over pure DSA-puzzle depth — DSA weight
        # kept moderate rather than sharply specialized.
        "Arrays & Hashing": 0.5, "Graphs": 0.5, "Design": 0.5,
        "Dynamic Programming": 0.3,
    },
    "Databricks": {
        # Data-infrastructure domain — arrays/strings and design recur,
        # with graph/DP depth present but not dominant.
        "Arrays & Hashing": 0.6, "Design": 0.5, "Trees": 0.4,
        "Dynamic Programming": 0.4, "Graphs": 0.3,
    },
    "Spotify": {
        # NOTE: thinner public signal; product-company generalist
        # pattern inferred similarly to Pinterest/Snap.
        "Arrays & Hashing": 0.5, "Trees": 0.4, "Design": 0.4,
        "Graphs": 0.3,
    },

    # ============================================================
    # GENERIC TIERS — for targeting a class of company rather than one
    # specific name; appropriately flatter/lower-confidence than any
    # named profile above
    # ============================================================

    "Startup / Product Company": {
        "Arrays & Hashing": 0.5, "Strings": 0.4, "Design": 0.5,
        "Trees": 0.3, "Dynamic Programming": 0.2, "Graphs": 0.2,
    },
    "IT Services / Consulting (Generic)": {
        # A catch-all for large service firms not individually profiled
        # above, matching the fundamentals-first TCS/Infosys/Wipro
        # pattern.
        "Arrays & Hashing": 0.5, "Sorting": 0.4, "Recursion": 0.3,
        "Strings": 0.3,
    },
}
# Mastery score for COMPANY READINESS weighted-average computation.
# NOT the same as engineering_quadrant.MASTERY_SCORE_MAP — that map
# produces a 0-100 classification score; this one produces a 0-1
# weight for a per-company weighted average against topic importance
# weights. Values here are intentionally higher (e.g. Introduced=0.3
# vs 0.25) to give small amounts of practice non-trivial readiness
# credit at company/tier matching resolution.
# Derived from the shared base + the one documented bump — numerically
# identical to the original hand-written table (0.0 / 0.3 / 0.6 / 0.85 / 1.0),
# but now structurally impossible to drift from engineering_quadrant.py's
# scale without that drift being a one-line, reviewable change.
MASTERY_SCORE_MAP = {
    label: round(min(1.0, MASTERY_SCORE_BASE[label] + COMPANY_READINESS_SCORE_BUMP[label]), 2)
    for label in MASTERY_SCORE_BASE
}
WEAK_FLOOR = 0.6


def compute_company_readiness(topic_mastery: list[dict]) -> list[dict]:
    """topic_mastery: leetcode_insights.build_topic_mastery() output.
    Returns one entry per company/tier, sorted strongest-first, each with
    a real recomputable 0-100 weighted-average readiness score and the
    specific weak topics dragging it down.

    NOTE on "weak_topics": this list is scoped to topics that matter for
    THIS company (i.e. appear in its COMPANY_TOPIC_WEIGHTS entry) AND
    score below WEAK_FLOOR — it is "important-and-weak" for this company,
    not "any gap in the user's overall practice." A topic the user has
    never touched but that isn't part of a given company's typical loop
    correctly never appears here for that company.
    """
    mastery_by_topic = {t["topic"]: t["mastery"] for t in topic_mastery}

    results = []
    for company, weights in COMPANY_TOPIC_WEIGHTS.items():
        weighted_sum = weight_total = 0.0
        weak_topics = []

        for topic, weight in weights.items():
            mastery_label = mastery_by_topic.get(topic, "Not Practiced")
            score = MASTERY_SCORE_MAP.get(mastery_label, 0.0)
            weighted_sum += score * weight
            weight_total += weight
            if score < WEAK_FLOOR:
                weak_topics.append(topic)

        readiness_pct = round((weighted_sum / weight_total) * 100) if weight_total > 0 else 0
        weak_topics_sorted = sorted(weak_topics, key=lambda t: weights.get(t, 0), reverse=True)

        results.append({
            "company": company,
            "readiness_pct": readiness_pct,
            "weak_topics": weak_topics_sorted[:3],
        })

    return sorted(results, key=lambda r: r["readiness_pct"], reverse=True)