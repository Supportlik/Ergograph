"""ATS (applicant tracking system) readability check.

Verifies that the text layer of a generated PDF contains ALL content
strings, i.e. that the document can be parsed by machines and not only
looked at by humans. Before matching, the generator's own page-number
stamps ("2 / 4") are stripped from the extracted text so that paragraphs
flowing across a page break still match as one string.
"""

from __future__ import annotations

import html
import re

#: Typographic forms that PDF text extraction may return differently
#: from the source string.
_EQUIVALENTS = {
    "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff",
    "ﬃ": "ffi", "ﬄ": "ffl",
    " ": " ",  # no-break space
}

#: <br> produces a line break in the PDF text layer, so it must become a
#: space; all other tags (e.g. inline <a>) wrap text without separating it.
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
#: The page-number stamp added by pdf.add_page_numbers, on a line of its own.
_PAGENUM_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$", re.MULTILINE)


def normalize(text: str) -> str:
    """Make source strings and extracted PDF text comparable.

    Collapses whitespace, maps ligatures, folds case (CSS may render text
    uppercase via text-transform) and joins hyphen line wraps
    ("Cloud-\\nInfrastruktur" extracts as "Cloud- Infrastruktur").
    Applied to both sides of the comparison, so it stays strict.
    """
    for src, dst in _EQUIVALENTS.items():
        text = text.replace(src, dst)
    text = _WS_RE.sub(" ", text)
    text = text.replace("- ", "-")
    return text.strip().casefold()


def plain_text(fragment) -> str:
    """Reduce a content value (a trusted HTML fragment) to its plain text."""
    text = _BR_RE.sub(" ", str(fragment))
    return normalize(html.unescape(_TAG_RE.sub("", text)))


def _paragraphs(description) -> list:
    return [description] if isinstance(description, str) else list(description)


def key_strings(name: str, content: dict, document: str) -> list[str]:
    """All strings that must be machine-readable in the given document.

    `content` is the language content with the facts already filtered to
    the built variant; `document` is a canonical key (cv/projects/skills/full).
    """
    lab = content["labels"]
    keys: list = [name, content["title"]]
    for c in content["contact"]:
        keys += [c["label"], c["value"]]
    if document in ("cv", "full"):
        keys.append(content["tagline"])
        keys += [lab[k] for k in ("facts", "languages", "certs", "core",
                                  "experience", "education", "publications")]
        for fact in content["facts"]:
            keys += [fact["label"], fact["value"]]
        for lang in content["languages"]:
            keys += [lang["name"], lang["level"]]
        for cert in content["certs"]:
            keys += [cert["name"], cert.get("description")]
        keys += list(content["top_skills"])
        for edu in content["education"]:
            keys += [edu["year"], edu["degree"], edu["institution"]]
        for entry in content["experience"]:
            keys += [entry["period"], entry["role"], entry["org"]]
            keys += list(entry["bullets"])
        for pub in content["publications"]:
            keys += [pub["title"], pub["venue"]]
    if document in ("projects", "full"):
        keys.append(lab["projects"])
        for group in content["projects"]:
            keys += [group["group"], group["meta"]]
            for item in group["items"]:
                keys += [item["title"], item["tech"]]
                keys += _paragraphs(item["description"])
    if document in ("skills", "full"):
        keys += [lab["skills"], lab["legend"]]
        for cat in content["skills"]:
            keys.append(cat["category"])
            for item in cat["items"]:
                keys += [item["name"], item.get("note")]
    return [plain_text(k) for k in keys if k is not None and str(k).strip()]


def missing_strings(pdf_text: str, expected: list[str]) -> list[str]:
    """Return the expected strings that are absent from the PDF text layer."""
    haystack = normalize(_PAGENUM_RE.sub(" ", pdf_text))
    return [s for s in expected if normalize(s) not in haystack]
