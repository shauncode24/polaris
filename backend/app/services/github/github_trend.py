"""Single definition of 'improving vs declining' trend comparison —
Engineering Identity fix #7. Before this existed, the Improving/Declining
labels were computed inline inside github_insights.py's
build_github_insights() (for documentation_trend / testing_trend, stored
on the sync snapshot). weekly_brief.py already, correctly, only ever
READS that stored trend rather than recomputing it — this module is what
makes that the structurally enforced path, rather than a coincidence
that could silently break the first time a future consumer needs a
trend and reaches for its own comparison instead of this function.
"""
from typing import Literal

Trend = Literal["Improving", "Declining", "Unchanged"]


def compute_trend(current_value: float | int, previous_value: float | int) -> Trend:
    if current_value > previous_value:
        return "Improving"
    if current_value < previous_value:
        return "Declining"
    return "Unchanged"