"""Shared text sanitizer for any AI-generated prose that might echo back
an internal bullet_id (e.g. exp_<uuid>_0) into user-facing text. Used by
resume review, narrative coherence, and tailoring — one implementation
so every surface strips these the same way instead of each re-inventing
its own regex.
"""
import re

_RAW_ID_TOKEN = r"['\"]?(?:exp|proj)_[a-fA-F0-9\-]{32,36}_\d+['\"]?"
_RAW_ID_PATTERN = re.compile(_RAW_ID_TOKEN)
_RAW_ID_LIST_PATTERN = re.compile(rf"\(\s*{_RAW_ID_TOKEN}(?:\s*,\s*{_RAW_ID_TOKEN})*\s*\)")


def sanitize_ai_text(text: str) -> str:
    if not text:
        return text
    cleaned = _RAW_ID_LIST_PATTERN.sub("", text)
    cleaned = _RAW_ID_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" ( )", "").replace("()", "").strip()
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    return cleaned.strip(", ")