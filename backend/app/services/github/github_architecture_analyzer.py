"""Architecture-depth assessment — the ONE place in the GitHub module
that reasons over real repository structure with an LLM, instead of
manifest-presence checks. Deliberately gated behind a deterministic
completeness bar (github_scoring.py's own quality_score) so LLM spend
is never wasted narrating throwaway or half-finished repos, and the
qualitative read is layered ON TOP of the deterministic score — it
never replaces or overrides it.

Input is file PATHS ONLY, never file contents — keeps the call cheap
and keeps the model from inferring quality it can't actually see.
"""
import json

from app.core.llm import chat_completion, MODEL

MIN_QUALITY_SCORE_FOR_ARCHITECTURE_PASS = 40
MAX_PATHS_IN_PROMPT = 150

ARCHITECTURE_SYSTEM_PROMPT = """You are a senior engineer reviewing a repository's file structure only —
you do NOT have file contents, only the list of file paths. You will receive a JSON object with the repo
name, its detected primary technologies, and a list of file paths (may be truncated/capped).

Judge ONLY what the paths actually show:
1. "depth_label": one of "flat_script" (little to no separation of concerns — e.g. one or two top-level
   files), "basic_structure" (a few folders but shallow separation), "layered" (clear separation of
   concerns, e.g. routers/services/models or components/hooks/utils), "well_architected" (layered AND
   shows tests, config separation, and clear domain boundaries).
2. "observations": 2-4 SPECIFIC observations that cite real folder/file names you were given — never a
   generic statement that doesn't reference the actual paths.
3. "confidence": "low" if the path list looks truncated, too sparse, or ambiguous to judge confidently,
   else "high".

You MUST NOT reference any file, folder, or technology not literally present in the input. If the path
list is too short or unclear, set depth_label to "basic_structure" and confidence to "low" rather than
guessing.

Output ONLY valid JSON, no prose, no markdown fences:
{"depth_label": str, "observations": [str], "confidence": str}"""


def is_eligible_for_architecture_pass(
    *, quality_score: float, is_archived: bool, is_fork: bool, contributed_as_fork: bool
) -> bool:
    """The deterministic gate. A repo must already show real, verified
    completeness before an LLM call is spent reasoning about its
    structure — mirrors github_scoring.py's rule that unverified
    activity never counts as evidence.
    """
    if is_archived:
        return False
    if is_fork and not contributed_as_fork:
        return False
    return quality_score >= MIN_QUALITY_SCORE_FOR_ARCHITECTURE_PASS


async def assess_architecture_depth(repo_name: str, technologies: list[str], file_paths: list[str]) -> dict | None:
    if not file_paths:
        return None

    sample_paths = sorted(file_paths)[:MAX_PATHS_IN_PROMPT]
    payload = {"repo_name": repo_name, "technologies": technologies, "file_paths": sample_paths}

    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": ARCHITECTURE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Architecture assessment for {repo_name}:\n{content}", flush=True)
        parsed = json.loads(content)
        if parsed.get("depth_label") not in {"flat_script", "basic_structure", "layered", "well_architected"}:
            return None
        return {
            "depth_label": parsed["depth_label"],
            "observations": parsed.get("observations", [])[:4],
            "confidence": parsed.get("confidence", "low"),
        }
    except Exception as e:
        print(f"[TRACING] Architecture assessment failed for {repo_name}, skipping: {e}", flush=True)
        return None