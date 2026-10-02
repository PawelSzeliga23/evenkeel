"""A pasted Claude answer: the Markdown inside its code fence, and how many of the expected sections it has."""
import re

from app.reviews.prompt import SECTIONS

_OPEN = re.compile(r"^(`{3,4})(?:markdown|md)?[ \t]*$", re.IGNORECASE | re.MULTILINE)
_KNOWN = {section.lower() for section in SECTIONS}


def clean(text: str) -> str:
    """The text inside the first fence of three or four backticks (prose around it dropped), else the text trimmed.
    The closing fence is the last line of the same backticks, so shorter code blocks inside stay whole."""
    opening = _OPEN.search(text)
    if opening is None:
        return text.strip()
    fence = opening.group(1)
    rest = text[opening.end():]
    closings = [m.start() for m in re.finditer(rf"^{fence}[ \t]*$", rest, re.MULTILINE)]
    return (rest[:closings[-1]] if closings else rest).strip()


def _title(line: str) -> str:
    """A level-2 heading's words: emoji, numbering and punctuation around them dropped, lower case."""
    return re.sub(r"^[^\wąćęłńóśźż]+|[^\wąćęłńóśźż]+$", "", line[3:].strip().lower())


def count_sections(text: str) -> int:
    found = {_title(line) for line in text.splitlines() if line.startswith("## ")}
    return len(found & _KNOWN)
