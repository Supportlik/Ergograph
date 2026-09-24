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
    # apostrophe forms: pypdf may extract U+2019 as U+02BC
    "’": "'", "ʼ": "'", "‘": "'",
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
    text = text.replace("– ", "–")  # line wraps after en dashes (e.g. date ranges)
    return text.strip().casefold()


def plain_text(fragment) -> str:
    """Reduce a content value (a trusted HTML fragment) to its plain text."""
    text = _BR_RE.sub(" ", str(fragment))
    return normalize(html.unescape(_TAG_RE.sub("", text)))


def _paragraphs(description) -> list:
    return [description] if isinstance(description, str) else list(description)


def key_strings(name: str, content: dict, document: str) -> list[str]:
    """All strings that must be machine-readable in the given document.

    `content` is the language content already resolved for the built
    variant; `document` is a canonical key (cv/projects/skills/full/onepager).
    """
    lab = content["labels"]
    keys: list = [name, content["title"]]
    for c in content["contact"]:
        keys += [c["label"], c["value"]]
    if document == "onepager":
        keys += _onepager_keys(content)
    if document in ("cv", "full"):
        keys.append(content["tagline"])
        # section labels only count when their section is non-empty (the
        # renderer hides empty sections and sidebar blocks)
        keys += [lab["experience"], lab["education"]]
        for key, label in (("facts", "facts"), ("languages", "languages"),
                           ("certs", "certs"), ("top_skills", "core"),
                           ("publications", "publications")):
            if content[key]:
                keys.append(lab[label])
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
            for b in entry["bullets"]:
                if isinstance(b, dict):
                    keys += [b["text"], b.get("org"), b.get("period")]
                else:
                    keys.append(b)
        for pub in content["publications"]:
            keys += [pub["title"], pub["venue"], pub.get("summary")]
    if document in ("projects", "full"):
        keys.append(lab["projects"])
        for group in content["projects"]:
            keys += [group["group"], group["meta"]]
            for item in group["items"]:
                keys += [item["title"], item.get("period"), item.get("org"), item["tech"]]
                keys += _paragraphs(item["description"])
    if document in ("skills", "full"):
        keys += [lab["skills"], lab["legend"]]
        for cat in content["skills"]:
            keys.append(cat["category"])
            for item in cat["items"]:
                keys += [item["name"], item.get("note")]
    return [plain_text(k) for k in keys if k is not None and str(k).strip()]


def _onepager_keys(content: dict) -> list:
    from .onepager import onepager_facts, reference_projects

    lab = content["labels"]
    block = content["onepager"]
    olab = block["labels"]
    keys: list = [block.get("summary") or content["tagline"], olab["competencies"],
                  olab["projects"]]
    facts = onepager_facts(content)
    if facts:
        keys.append(lab["facts"])
    for fact in facts:
        keys += [fact["label"], fact["value"]]
    for h in block.get("highlights") or []:
        keys += [h["value"], h["label"]]
    for cl in block.get("competencies") or []:
        keys += [cl["name"], *(cl.get("items") or [])]
    for proj in reference_projects(content):
        keys += [proj["title"], proj["period"], proj["org"], proj["role"],
                 proj["description"], proj["tech"], *proj["bullets"]]
    if content["certs"]:
        keys.append(lab["certs"])
    for cert in content["certs"]:
        keys += [cert["name"], cert.get("description")]
    if content["languages"]:
        keys.append(lab["languages"])
    for lang in content["languages"]:
        keys += [lang["name"], lang["level"]]
    for box in block.get("extra") or []:
        keys += [box["title"], *(box.get("items") or [])]
    if block.get("timeline"):
        keys.append(olab["timeline"])
    for st in block.get("timeline") or []:
        keys += [st["period"], st["label"], st.get("sub"), st.get("track")]
    keys.append(olab.get("legend"))
    return keys


def missing_strings_md(markdown_text: str, expected: list[str]) -> list[str]:
    """Like `missing_strings`, for the Markdown export. The export writes a
    `<br>` as a comma, so commas are ignored on both sides of the check."""
    from .markdown import plain

    haystack = normalize(plain(markdown_text)).replace(",", "")
    return [s for s in expected
            if normalize(s).replace(",", "") not in haystack]


def leaked_identity(text: str, markers: list[str]) -> list[str]:
    """The identity markers (name parts, contact values) found in `text`."""
    haystack = normalize(text)
    return [m for m in markers if normalize(m) and normalize(m) in haystack]


def missing_strings(pdf_text: str, expected: list[str]) -> list[str]:
    """Return the expected strings that are absent from the PDF text layer."""
    haystack = normalize(_PAGENUM_RE.sub(" ", pdf_text))
    return [s for s in expected if normalize(s) not in haystack]
