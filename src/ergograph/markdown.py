"""Markdown export: the same documents as plain, copy-paste-ready text.

Meant for the places a PDF cannot go: portal forms, the body of a mail, a
prompt. The markup is deliberately sparse (headings, bullets, bold names,
links) so the text still reads cleanly where Markdown is not rendered.
Section order follows `render.py`, as the DOCX does.
"""

from __future__ import annotations

import html
import re

from .onepager import onepager_facts, reference_projects

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LINK_RE = re.compile(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_BOLD_RE = re.compile(r"</?(b|strong)>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def md(fragment) -> str:
    """A content value (trusted HTML fragment) as Markdown inline text."""
    text = _BR_RE.sub(", ", str(fragment))

    def link(match):
        url, label = match.group(1), _TAG_RE.sub("", match.group(2))
        return label if url.startswith(("mailto:", "tel:")) else f"[{label}]({url})"

    text = _LINK_RE.sub(link, text)
    text = _BOLD_RE.sub("**", text)
    return html.unescape(_TAG_RE.sub("", text)).strip()


def plain(markdown_text: str) -> str:
    """Markdown back to its visible text, for the content-identity check."""
    return _MD_LINK_RE.sub(r"\1", markdown_text).replace("**", "")


def _link(value, url) -> str:
    text = md(value)
    if not url or url.startswith(("mailto:", "tel:")):
        return text
    return f"[{text}]({url})"


def _header(name: str, content: dict) -> list[str]:
    out = [f"# {md(name)}", "", f"**{md(content['title'])}**", ""]
    for c in content["contact"]:
        out.append(f"- {md(c['label'])}: {_link(c['value'], c.get('url'))}")
    if content["contact"]:
        out.append("")
    return out


def _facts(content: dict, facts: list | None = None) -> list[str]:
    lab = content["labels"]
    facts = content["facts"] if facts is None else facts
    out = []
    if facts:
        out += [f"## {md(lab['facts'])}", ""]
        out += [f"- {md(f['label'])}: {md(f['value'])}" for f in facts]
        out.append("")
    return out


def _certs_langs(content: dict) -> list[str]:
    lab = content["labels"]
    out = []
    if content["certs"]:
        out += [f"## {md(lab['certs'])}", ""]
        for c in content["certs"]:
            desc = f" ({md(c['description'])})" if c.get("description") else ""
            out.append(f"- {_link(c['name'], c.get('url'))}{desc}")
        out.append("")
    if content["languages"]:
        out += [f"## {md(lab['languages'])}", ""]
        out += [f"- {md(x['name'])}: {md(x['level'])}" for x in content["languages"]]
        out.append("")
    return out


def _cv(content: dict) -> list[str]:
    lab = content["labels"]
    out = [md(content["tagline"]), ""]
    out += _facts(content)
    out += _certs_langs(content)
    if content["top_skills"]:
        out += [f"## {md(lab['core'])}", "",
                " · ".join(md(s) for s in content["top_skills"]), ""]
    out += [f"## {md(lab['experience'])}", ""]
    for entry in content["experience"]:
        out += [f"### {md(entry['role'])}", "",
                f"{md(entry['org'])} · {md(entry['period'])}", ""]
        for b in entry["bullets"]:
            if isinstance(b, dict):
                meta = " · ".join(md(x) for x in (b.get("org"), b.get("period")) if x)
                out.append(f"- {md(b['text'])}" + (f" ({meta})" if meta else ""))
            else:
                out.append(f"- {md(b)}")
        out.append("")
    out += [f"## {md(lab['education'])}", ""]
    out += [f"- {md(e['year'])}: {md(e['degree'])}, {md(e['institution'])}"
            for e in content["education"]]
    out.append("")
    if content["publications"]:
        out += [f"## {md(lab['publications'])}", ""]
        for pub in content["publications"]:
            line = f"- **{md(pub['title'])}.** {md(pub['venue'])}."
            if pub.get("url"):
                line += f" {pub['url']}"
            if pub.get("summary"):
                line += f" {md(pub['summary'])}"
            out.append(line)
        out.append("")
    return out


def _paragraphs(description) -> list:
    return [description] if isinstance(description, str) else list(description)


def _projects(content: dict) -> list[str]:
    out = [f"## {md(content['labels']['projects'])}", ""]
    for group in content["projects"]:
        out += [f"### {md(group['group'])}", "", md(group["meta"]), ""]
        for item in group["items"]:
            meta = " · ".join(md(x) for x in (item.get("org"), item.get("period")) if x)
            out += [f"**{md(item['title'])}**" + (f" ({meta})" if meta else ""), ""]
            out += [md(p) for p in _paragraphs(item["description"])]
            out += ["", md(item["tech"]), ""]
    return out


def _skills(content: dict) -> list[str]:
    lab = content["labels"]
    out = [f"## {md(lab['skills'])}", "", md(lab["legend"]), ""]
    for cat in content["skills"]:
        out += [f"### {md(cat['category'])}", ""]
        for item in cat["items"]:
            note = f" ({md(item['note'])})" if item.get("note") else ""
            out.append(f"- {md(item['name'])}: {float(item['level']):g}{note}")
        out.append("")
    return out


def _onepager(content: dict) -> list[str]:
    block = content["onepager"]
    lab = block["labels"]
    out = [md(block.get("summary") or content["tagline"]), ""]
    if block.get("highlights"):
        out += [" · ".join(f"**{md(h['value'])}** {md(h['label'])}"
                           for h in block["highlights"]), ""]
    out += _facts(content, onepager_facts(content))
    out += [f"## {md(lab['competencies'])}", ""]
    for cl in block.get("competencies") or []:
        level = f" ({float(cl['level']):g})" if cl.get("level") is not None else ""
        items = ", ".join(md(t) for t in cl.get("items") or [])
        out.append(f"- **{md(cl['name'])}**{level}" + (f": {items}" if items else ""))
    if lab.get("legend"):
        out += ["", md(lab["legend"])]
    out += ["", f"## {md(lab['projects'])}", ""]
    for proj in reference_projects(content):
        meta = " · ".join(md(x) for x in (proj["role"], proj["org"], proj["period"]) if x)
        out += [f"**{md(proj['title'])}**" + (f" ({meta})" if meta else ""), ""]
        if proj["description"]:
            out += [md(proj["description"]), ""]
        out += [f"- {md(b)}" for b in proj["bullets"]]
        if proj["tech"]:
            out += ["", md(proj["tech"])]
        out.append("")
    out += _certs_langs(content)
    for box in block.get("extra") or []:
        out += [f"## {md(box['title'])}", ""]
        out += [f"- {md(r)}" for r in box.get("items") or []]
        out.append("")
    if block.get("timeline"):
        out += [f"## {md(lab['timeline'])}", ""]
        from .onepager import timeline_tracks
        for track, stations in timeline_tracks(block["timeline"]):
            if track:
                out += [f"### {md(track)}", ""]
            for s in stations:
                sub = f", {md(s['sub'])}" if s.get("sub") else ""
                out.append(f"- {md(s['period'])}: {md(s['label'])}{sub}")
            out.append("")
        out.append("")
    return out


def build_markdown(name: str, content: dict, document: str) -> str:
    parts = {"cv": [_cv], "projects": [_projects], "skills": [_skills],
             "full": [_cv, _projects, _skills], "onepager": [_onepager]}[document]
    lines = _header(name, content)
    for part in parts:
        lines += part(content)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
