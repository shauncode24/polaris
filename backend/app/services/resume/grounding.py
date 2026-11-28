"""Checks a tailored resume against the user's record, without a model.

`check_rewrite` compares a rewrite with the bullet it rewords, word by word.
A figure the bullet doesn't state means the rewrite is dropped. Any other word
added or left out, or the same words in a different order, is flagged for the
user to confirm. Only another spelling of the same name ("Postgres",
"PostgreSQL") passes unflagged.

It deliberately compares the words themselves, not the skills they stand for:
"version control" counts as evidence of Git, but doesn't say Git. So a fair
paraphrase is flagged too. That costs the user a look; letting an unsupported
claim through would cost more.

`unsupported_sources` checks that what a document cites is really there.
"""
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.resume.tailored import ResumeLine, SourceRef, TailoredResumeDocument
from app.services.resume.skill_names import NAME_OF
from app.services.resume.sources import cited_rows, row_bullets

_NUMBER_WORDS = {
    word: str(number) for number, word in enumerate(
        "one two three four five six seven eight nine ten eleven twelve".split(), start=1,
    )
}
# Words a rewrite may add or drop freely. "the" is not one: "a lead developer"
# and "the lead developer" claim different things.
_IGNORED = {"a", "an", "and"}

_SPELLINGS = "|".join(
    r"\s+".join(map(re.escape, spelling.split(" "))) for spelling in sorted(NAME_OF, key=len, reverse=True)
)
_TOKEN = re.compile(
    # A listed spelling standing on its own, not part of a longer word.
    rf"(?P<name>(?<![^\W_])(?<![.\-])(?:{_SPELLINGS})(?![^\W_]|[+#]|[.\-][^\W_]))"
    r"|(?P<figure>(?:(?<![\w.])\.)?\d+(?:[.,]\d+)*)"
    r"|(?P<word>\.?[^\W\d_][^\W_]*(?:[.'\-][^\W_]+)*[+#]*)"
    # Any other mark that can change a claim ("~", "<", "#", "$", "×", an arrow):
    # everything but spaces and ordinary punctuation.
    r"""|(?P<sign>[^\w\s.,;:!?'"“”‘()\[\]{}\-–—/\|&*•·`])""",
    re.IGNORECASE,
)


class _Token(NamedTuple):
    key: str  # what it means, for comparing
    shown: str  # as written
    is_figure: bool = False


def _tokens(text: str) -> list[_Token]:
    tokens = []
    for match in _TOKEN.finditer(unicodedata.normalize("NFKC", text).replace("’", "'")):
        shown = match.group(0)
        lower = " ".join(shown.lower().split())
        # Written small, "react" is the verb rather than the library.
        if match.lastgroup == "name" and shown != "react":
            tokens.append(_Token(NAME_OF[lower], shown))
        elif match.lastgroup == "figure":
            # Commas between thousands only: "1,5" is not 15.
            tokens.append(_Token(re.sub(r",(?=\d{3}(?!\d))", "", lower), shown, is_figure=True))
        elif lower in _NUMBER_WORDS:
            tokens.append(_Token(_NUMBER_WORDS[lower], shown, is_figure=True))
        elif lower not in _IGNORED:
            tokens.append(_Token(lower, shown))
    return tokens


def _only_in(first: list[_Token], second: list[_Token]) -> list[str]:
    """The words of `first`, as written and in order, that `second` has fewer of."""
    spare = Counter(t.key for t in first) - Counter(t.key for t in second)
    found = []
    for token in reversed(first):  # of a repeated word, the later copies are the extra ones
        if spare[token.key] > 0:
            spare[token.key] -= 1
            found.append(token.shown)
    return found[::-1]


def _quoted(words: list[str]) -> str:
    return ", ".join(f'"{word}"' for word in dict.fromkeys(words))


@dataclass(frozen=True)
class RewriteCheck:
    new_figures: list[str]  # figures the original doesn't state
    flags: list[str]  # what the user has to confirm, in words for them


def check_rewrite(original: str, rewrite: str) -> RewriteCheck:
    before, after = _tokens(original), _tokens(rewrite)
    stated = {t.key for t in before if t.is_figure}
    new_figures = [t.shown for t in after if t.is_figure and t.key not in stated]

    flags = []
    added, left_out = _only_in(after, before), _only_in(before, after)
    if added:
        flags.append(f"Adds what your bullet doesn't say: {_quoted(added)}.")
    if left_out:
        flags.append(f"Leaves out: {_quoted(left_out)}.")
    if not flags and [t.key for t in before] != [t.key for t in after]:
        flags.append("Puts your words in a different order. Check that it still says what you did.")
    return RewriteCheck(new_figures, flags)


def ground_line(line: ResumeLine) -> None:
    """Sets the line's flags from its rewrite, replacing any it came with. A
    rewrite with a figure the original doesn't state is removed; on a line with
    no original there is nothing to fall back to, so it is only flagged.
    """
    if not (line.rewrite or "").strip():
        line.flags = []
        return
    original = (line.original or "").strip()
    check = check_rewrite(original, line.rewrite)
    if original and check.new_figures:
        line.rewrite, line.decision, line.flags = None, "pending", []
    else:
        line.flags = check.flags


async def unsupported_sources(db: AsyncSession, user_id, document: TailoredResumeDocument) -> list[str]:
    """What `document` cites that the user's record doesn't have: an item that
    is missing, hidden or someone else's, or a line whose original wording is
    not that of a bullet it cites. Empty when every citation holds.

    An entry's headings (role, company, dates, technologies) and skill names
    are not compared with the rows they cite.
    """
    entries = [*document.experience, *document.projects, *document.education, *document.skills]
    lines = document.lines()
    refs: list[SourceRef] = [ref for item in [*entries, *lines] for ref in item.sources]

    rows = await cited_rows(db, user_id, refs)

    def cited_bullet(ref: SourceRef) -> str | None:
        row = rows.get((ref.kind, ref.id))
        if row is None or ref.bullet is None:
            return None
        bullets = row_bullets(ref.kind, row)
        return (bullets[ref.bullet] or "").strip() if ref.bullet < len(bullets) else None

    # LeetCode practice has no row of its own, so a source naming one is wrong.
    problems = [
        f"{ref.kind} {ref.id} is not in the record"
        for ref in refs
        if ref.id is not None and (ref.kind, ref.id) not in rows
    ]
    problems += [
        f"line {line.id} does not quote a bullet it cites"
        for line in lines
        if line.original is not None and line.original.strip() not in {cited_bullet(ref) for ref in line.sources}
    ]
    return list(dict.fromkeys(problems))
