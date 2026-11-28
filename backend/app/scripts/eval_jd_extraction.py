"""Runs the real job-description pipeline over a folder of postings and scores
the skills it produces against hand-written expectations.

From backend/:

    DATABASE_URL=postgresql://test:test@localhost:55432/polaris_eval_test \\
        uv run python -m app.scripts.eval_jd_extraction

Put one posting per .txt file in eval/jd_extraction/jds/ (not committed: the
text belongs to whoever posted it). Expectations for a file go in
eval/jd_extraction/gold.json under its name; a file without any is still run
and listed, just not scored.

LLM replies are cached in eval/jd_extraction/cache/, keyed on the exact
request, so a rerun after a code-only change costs nothing and a prompt change
is picked up automatically. `--fresh` ignores the cache.

It writes to the database it is given (it empties `skill_aliases` first, so a
run never depends on an earlier one), and therefore refuses any database that
is not local with "eval" or "test" in its name.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2] / "eval" / "jd_extraction"
BANDS = {
    "required": "enriched_required_skills",
    "nice_to_have": "enriched_nice_to_have",
}


def _require_disposable_database() -> None:
    url = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(url)
    name = parsed.path.lstrip("/").lower()
    if parsed.hostname not in ("localhost", "127.0.0.1") or not ("eval" in name or "test" in name):
        sys.exit(
            "Set DATABASE_URL to a local database with 'eval' or 'test' in its name. "
            "This script writes to it."
        )


_require_disposable_database()

from app.core import settings as _settings  # noqa: E402,F401  (loads .env before the LLM client is built)
from app.core import llm  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.facts import User  # noqa: E402
from app.models.structure import SkillAlias  # noqa: E402
from app.services.evidence.matching import mentions_skill  # noqa: E402
from app.services.job_intelligence import extraction  # noqa: E402
from app.services.job_intelligence.builder import build_job_intelligence  # noqa: E402
from app.services.job_intelligence.cleanup import plain_text  # noqa: E402
from sqlalchemy import delete  # noqa: E402


def _is_cut_off(content: str) -> bool:
    try:
        payload = json.loads(content)
    except ValueError:
        return True
    return "job" in payload and not extraction.is_complete_reply(payload)


def _install_cache(fresh: bool) -> dict:
    """Wraps the app's one model request with a disk cache."""
    stats = {"called": 0, "cached": 0}
    cache = ROOT / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    llm.client = llm.build_client(max_retries=8, timeout=120)
    real = llm.chat_completion

    class _Reply:
        def __init__(self, content: str):
            message = type("Message", (), {"content": content})()
            self.choices = [type("Choice", (), {"message": message})()]

    async def cached_completion(**kwargs):
        key = hashlib.sha256(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()[:24]
        path = cache / f"{key}.json"
        if path.exists() and not fresh:
            stats["cached"] += 1
            return _Reply(path.read_text(encoding="utf8"))
        response = await real(**kwargs)
        stats["called"] += 1
        content = response.choices[0].message.content or ""
        if not _is_cut_off(content):  # so a retry, or the next run, asks again
            path.write_text(content, encoding="utf8")
        return response

    llm.chat_completion = cached_completion
    return stats


def _score(profile, expected: dict, text: str) -> dict:
    """Compares canonical names, because that is what the skill gap matches on:
    a skill that appears only under some other name counts as missed.
    """
    canonicals = {
        band: {s.canonical for s in getattr(profile, field)} for band, field in BANDS.items()
    }
    implicit = {s.canonical for s in profile.enriched_implicit_skills}
    result = {"hit": 0, "total": 0, "wrong_band": [], "missed": [], "extra": [], "ungrounded": []}
    accounted: set[str] = set()
    for band in BANDS:
        for entry in expected.get(band, []):
            names = set(entry.split("|"))
            accounted |= names
            result["total"] += 1
            if names & canonicals[band]:
                result["hit"] += 1
                continue
            other = next((b for b in BANDS if b != band and names & canonicals[b]), None)
            if other or names & implicit:
                result["wrong_band"].append(f"{entry.split('|')[0]} (expected {band}, got {other or 'implicit'})")
            else:
                result["missed"].append(entry.split("|")[0])
    for band, field in BANDS.items():
        for skill in getattr(profile, field):
            if skill.canonical not in accounted:
                result["extra"].append(f"{skill.raw!r} -> {skill.canonical} [{band}]")
            source = plain_text(text)
            words = [w for w in skill.raw.replace("/", " ").replace("-", " ").split() if len(w) > 2]
            if words and not mentions_skill(source, skill.raw) and not any(w.lower() in source.lower() for w in words):
                result["ungrounded"].append(f"{skill.raw!r} [{band}]")
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fresh", action="store_true", help="ignore cached LLM replies")
    parser.add_argument("--only", help="run files whose name contains this")
    args = parser.parse_args()

    stats = _install_cache(args.fresh)
    gold = json.loads((ROOT / "gold.json").read_text(encoding="utf8"))
    files = sorted((ROOT / "jds").glob("*.txt"))
    if args.only:
        files = [f for f in files if args.only in f.stem]
    if not files:
        sys.exit(f"No .txt files in {ROOT / 'jds'}")

    lines: list[str] = []
    hit = total = extras = ungrounded = failed = 0
    async with AsyncSessionLocal() as db:
        await db.execute(delete(SkillAlias))
        user = User(email=f"eval-{uuid4().hex[:8]}@example.com", name="JD evaluation")
        db.add(user)
        await db.commit()
        user_id = user.id

        for path in files:
            text = path.read_text(encoding="utf8")
            try:
                profile, _company = await build_job_intelligence(db, user_id, text)
            except Exception as e:  # a failed posting is a finding, not a reason to stop
                await db.rollback()
                failed += 1
                lines.append(f"\n## {path.stem}\n\nFAILED: {e}")
                print(f"{path.stem}: FAILED {str(e)[:200]}")
                continue

            lines.append(f"\n## {path.stem}\n")
            lines.append(f"role={profile.role!r} company={profile.company!r} "
                         f"seniority={profile.seniority_signal.level} quality={profile.extraction_quality.label}")
            for label, group in (("required", profile.enriched_required_skills),
                                 ("implicit", profile.enriched_implicit_skills),
                                 ("nice_to_have", profile.enriched_nice_to_have)):
                lines.append(f"\n**{label}** ({len(group)})")
                lines.extend(f"- {s.raw} -> `{s.canonical}`" for s in group)

            if path.stem not in gold:
                print(f"{path.stem}: run (no expectations)")
                continue
            score = _score(profile, gold[path.stem], text)
            hit += score["hit"]
            total += score["total"]
            extras += len(score["extra"])
            ungrounded += len(score["ungrounded"])
            for key in ("missed", "wrong_band", "extra", "ungrounded"):
                if score[key]:
                    lines.append(f"\n{key}: " + "; ".join(score[key]))
            print(f"{path.stem}: {score['hit']}/{score['total']} expected, missed {len(score['missed'])}, "
                  f"wrong band {len(score['wrong_band'])}, extra {len(score['extra'])}, "
                  f"ungrounded {len(score['ungrounded'])}")

    recall = f"{hit}/{total} ({hit / total:.0%})" if total else "n/a"
    summary = (f"expected skills found in the right band: {recall}; extra items: {extras}; "
               f"ungrounded: {ungrounded}; failed postings: {failed}; "
               f"LLM calls: {stats['called']} new, {stats['cached']} cached")
    report = ROOT / "report.md"
    report.write_text("# JD extraction report\n\n" + summary + "\n" + "\n".join(lines) + "\n", encoding="utf8")
    print(f"\n{summary}\nFull report: {report}")


if __name__ == "__main__":
    asyncio.run(main())
