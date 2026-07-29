"""Deterministic keep/feature/hide ranking across a user's whole project
portfolio — the same "these are diluting your strongest work" signal
resume/analysis/dilution.py already computes for bullets, applied here
to projects. No LLM call: tier and rating are already real, verified
facts from github_scoring.py / projects/scoring.py; this module only
thresholds and ranks what's already computed.
"""

WEAK_TIERS = {"Prototype", "Archived"}
MIN_DESCRIPTION_LENGTH = 60
DILUTION_WARNING_THRESHOLD = 3


def _is_weak(card) -> bool:
    thin_description = not card.description or len(card.description) < MIN_DESCRIPTION_LENGTH
    return card.tier in WEAK_TIERS and not card.has_repo and thin_description


def compute_curation(cards: list) -> dict:
    """cards: list[ProjectCard] (already scored by overview.py).
    Returns {"items": [{project_id, project_name, action, reason}],
    "dilution_warning": str | None}.
    """
    items = []
    weak_count = 0
    featured_count = sum(1 for c in cards if c.is_featured)

    for card in cards:
        if card.is_featured:
            action, reason = "feature", "Ranks among your strongest projects by evidence and activity."
        elif _is_weak(card):
            action, reason = (
                "hide_suggested",
                f"{card.tier.lower()} with no linked repository and a thin description — "
                "likely diluting attention from your stronger work.",
            )
            weak_count += 1
        else:
            action, reason = "keep", "Solid supporting evidence for this project."

        items.append({
            "project_id": card.id,
            "project_name": card.name,
            "action": action,
            "reason": reason,
        })

    dilution_warning = None
    if weak_count >= DILUTION_WARNING_THRESHOLD:
        dilution_warning = (
            f"{weak_count} projects are low-evidence and undifferentiated — consider hiding or "
            f"consolidating them so your {featured_count} strongest project(s) get more attention."
        )

    return {"items": items, "dilution_warning": dilution_warning}