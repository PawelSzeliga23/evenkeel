"""A pasted Claude answer: the Markdown inside its code fence, and how many of the expected sections it has."""
import re

from app.reviews.prompt import SECTIONS

_OPEN = re.compile(r"^(`{3,4}|~{3,4})(?:markdown|md)?[ \t]*$", re.IGNORECASE | re.MULTILINE)
_KNOWN = {section.lower() for section in SECTIONS}


def clean(text: str) -> str:
    """The text inside the first fence of three or four backticks or tildes (prose around it dropped), else the text
    trimmed. The closing fence is the last line of the same fence, so shorter code blocks inside stay whole."""
    text = text.replace("\r\n", "\n")
    opening = _OPEN.search(text)
    heading = re.search(r"^## ", text, re.MULTILINE)
    # A fence after the first heading is a code block inside an answer copied without its wrapper: keep it all.
    if opening is None or (heading is not None and heading.start() < opening.start()):
        return text.strip()
    fence = opening.group(1)
    rest = text[opening.end():]
    closings = [m.start() for m in re.finditer(rf"^{fence}[ \t]*$", rest, re.MULTILINE)]
    return (rest[:closings[-1]] if closings else rest).strip()


def _title(line: str) -> str:
    """A level-2 heading's words: emoji, numbering and punctuation around them dropped, lower case."""
    return re.sub(r"^[^a-ząćęłńóśźż]+|[^a-ząćęłńóśźż]+$", "", line[3:].strip().lower())


def count_sections(text: str) -> int:
    found = {_title(line) for line in text.splitlines() if line.startswith("## ")}
    return len(found & _KNOWN)


def summary(text: str) -> str | None:
    """The text of the „W skrócie” section, without its heading, up to the next `## `; None without one."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## ") and _title(line) == SECTIONS[0].lower():
            body: list[str] = []
            for rest in lines[index + 1:]:
                if rest.startswith("## "):
                    break
                body.append(rest)
            return "\n".join(body).strip() or None
    return None
