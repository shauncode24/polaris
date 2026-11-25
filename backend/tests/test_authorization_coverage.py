"""Fails when a route with a path parameter has no authorization case."""
import re

from app.main import app
from tests.authorization_cases import CASES, EXEMPT


def _normalise(path: str) -> str:
    path = path.split("?")[0]
    return re.sub(r"\{[^}]+\}", "{}", path)


def test_every_parameterised_route_has_an_authorization_case():
    covered = {(c.method, _normalise(c.path)) for c in CASES}

    uncovered = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if "{" not in path:
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            if (method, _normalise(path)) not in covered and (method, _normalise(path)) not in EXEMPT:
                uncovered.append(f"{method} {path}")

    assert not uncovered, (
        "These routes take an ID but have no case in tests/authorization_cases.py, "
        "so nothing proves another user cannot reach them:\n  " + "\n  ".join(sorted(uncovered))
    )
