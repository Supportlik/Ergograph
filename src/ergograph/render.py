"""HTML rendering: builds the four documents from the YAML content.

Content values are inserted as trusted HTML fragments (local, personal
data); inline HTML such as `<a href="...">` is allowed.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from .config import ConfigError

PAGE_BREAK = '<div class="page-break"></div>'
#: Spacer between the parts of the combined dossier: the sections flow
#: continuously (no half-empty pages) but stay visually separated.
SECTION_GAP = '<div class="section-gap"></div>'


def load_theme(theme: str, base_dir: Path | None = None) -> str:
    """Load a theme: either a bundled one (`modern`) or a custom CSS file
    (path relative to the config.yaml)."""
    if theme.endswith(".css"):
        path = Path(theme)
        if base_dir is not None and not path.is_absolute():
            path = base_dir / path
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ConfigError(f"Theme file not found: {path}") from None
    ref = resources.files("ergograph").joinpath("themes", f"{theme}.css")
    if not ref.is_file():
        raise ConfigError(f"Unknown theme '{theme}'")
    return ref.read_text(encoding="utf-8")


def _link(value: str, url: str | None) -> str:
    return f'<a href="{url}">{value}</a>' if url else value


def header_html(name: str, content: dict) -> str:
    parts = "".join(
        f'<span><b>{c["label"]}:</b> {_link(c["value"], c.get("url"))}</span>'
        for c in content["contact"])
    return (f'<div class="header"><div class="name">{name}</div>'
            f'<div class="title">{content["title"]}</div>'
            f'<div class="contact">{parts}</div></div>')


def sidebar_html(content: dict) -> str:
    lab = content["labels"]
    facts = "".join(
        f'<div class="row"><span class="k">{f["label"]}</span>'
        f'<span class="v">{f["value"]}</span></div>'
        for f in content["facts"])
    langs = "".join(
        f'<div class="row"><span class="v">{l["name"]}</span> '
        f'<span style="color:#64748b">{l["level"]}</span></div>'
        for l in content["languages"])
    cert_items = []
    for cert in content["certs"]:
        url = cert.get("url")
        name = _link(cert["name"], url)
        desc = cert.get("description") or ""
        ds = f"<span>{desc}</span>" if desc else ""
        verify = f'<a class="verify" href="{url}">↗ {lab["verify"]}</a>' if url else ""
        cert_items.append(f'<div class="cert"><b>{name}</b>{ds}{verify}</div>')
    tags = "".join(f'<span class="tag">{s}</span>' for s in content["top_skills"])
    blocks = []
    if content["facts"]:
        blocks.append(f'<div class="block"><h3>{lab["facts"]}</h3>{facts}</div>')
    if content["languages"]:
        blocks.append(f'<div class="block"><h3>{lab["languages"]}</h3>{langs}</div>')
    if content["certs"]:
        blocks.append(f'<div class="block"><h3>{lab["certs"]}</h3>{"".join(cert_items)}</div>')
    if content["top_skills"]:
        blocks.append(f'<div class="block"><h3>{lab["core"]}</h3><div class="tags">{tags}</div></div>')
    return f'<div class="side">{"".join(blocks)}</div>'


def _bullet_html(bullet) -> str:
    """A bullet is a plain string or {text, org?, period?}; org renders as a
    small subtitle line, period right-aligned next to the text."""
    if not isinstance(bullet, dict):
        return f'<li>{bullet}</li>'
    head = f'<span>{bullet["text"]}</span>'
    if bullet.get("period"):
        head += f'<span class="li-period">{bullet["period"]}</span>'
    li = f'<div class="li-head">{head}</div>'
    if bullet.get("org"):
        li += f'<div class="li-sub">{bullet["org"]}</div>'
    return f'<li>{li}</li>'


def experience_html(content: dict) -> str:
    out = []
    for entry in content["experience"]:
        lis = "".join(_bullet_html(b) for b in entry["bullets"])
        out.append(
            f'<div class="entry"><div class="top"><span class="role">{entry["role"]}</span>'
            f'<span class="period">{entry["period"]}</span></div>'
            f'<div class="org">{entry["org"]}</div><ul>{lis}</ul></div>')
    return "".join(out)


def education_html(content: dict) -> str:
    return "".join(
        f'<div class="edu"><div class="y">{e["year"]}</div>'
        f'<div class="d"><b>{e["degree"]}</b><span>{e["institution"]}</span></div></div>'
        for e in content["education"])


def publications_html(content: dict) -> str:
    lab = content["labels"]
    items = []
    for pub in content["publications"]:
        url = pub.get("url")
        link = f' <a class="verify" href="{url}">↗ {lab["link"]}</a>' if url else ""
        summary = pub.get("summary")
        sum_html = f'<div class="pub-summary">{summary}</div>' if summary else ""
        items.append(f'<li><b>{pub["title"]}.</b> {pub["venue"]}.{link}{sum_html}</li>')
    return f'<div class="entry"><ul>{"".join(items)}</ul></div>'


def cv_section(content: dict) -> str:
    lab = content["labels"]
    pubs = (f'<h2 class="section">{lab["publications"]}</h2>{publications_html(content)}'
            if content["publications"] else "")
    return (f'<div class="profile">{content["tagline"]}</div>'
            f'<div class="cv-grid">{sidebar_html(content)}'
            f'<div class="main"><h2 class="section">{lab["experience"]}</h2>{experience_html(content)}'
            f'<h2 class="section">{lab["education"]}</h2>{education_html(content)}'
            f'{pubs}</div></div>')


def _paragraphs(description: str | list[str]) -> list[str]:
    if isinstance(description, str):
        return [description]
    return list(description)


def projects_section(content: dict) -> str:
    lab = content["labels"]
    out = [f'<h2 class="section">{lab["projects"]}</h2>']
    for group in content["projects"]:
        inner = []
        for item in group["items"]:
            pd_html = "".join(f'<div class="pd">{p.strip()}</div>'
                              for p in _paragraphs(item["description"]))
            top = f'<span class="ph">{item["title"]}</span>'
            if item.get("period"):
                top += f'<span class="pp">{item["period"]}</span>'
            org = f'<div class="po">{item["org"]}</div>' if item.get("org") else ""
            inner.append(f'<div class="proj"><div class="proj-top">{top}</div>'
                         f'{org}{pd_html}<div class="pt">{item["tech"]}</div></div>')
        out.append(f'<div class="proj-group"><div class="gh">{group["group"]}</div>'
                   f'<div class="gm">{group["meta"]}</div>{"".join(inner)}</div>')
    return "".join(out)


def skills_section(content: dict, level_max: float) -> str:
    lab = content["labels"]
    out = [f'<h2 class="section">{lab["skills"]}</h2>',
           f'<div class="legend">{lab["legend"]}</div>',
           '<div class="skills-cols">']
    for cat in content["skills"]:
        rows = []
        for item in cat["items"]:
            level = float(item["level"])
            pct = round(level / level_max * 100)
            lvlstr = f"{level:g}"
            note = item.get("note") or ""
            rows.append(f'<div class="skill"><span class="sn">{item["name"]}</span>'
                        f'<span class="bar"><i style="width:{pct}%"></i></span>'
                        f'<span class="lvl">{lvlstr}</span>'
                        f'<span class="note">{note}</span></div>')
        out.append(f'<div class="skill-cat"><h3>{cat["category"]}</h3>{"".join(rows)}</div>')
    out.append('</div>')
    return "".join(out)


def build_documents(name: str, content: dict, level_max: float) -> dict[str, str]:
    """Build all four document bodies (without the <html> frame)."""
    header = header_html(name, content)
    cv = cv_section(content)
    projects = projects_section(content)
    skills = skills_section(content, level_max)
    return {
        "cv": header + cv,
        "projects": header + projects,
        "skills": header + skills,
        # each part of the combined dossier starts on a fresh page
        "full": header + cv + PAGE_BREAK + projects + PAGE_BREAK + skills,
    }


def page(title: str, body: str, css: str, lang: str) -> str:
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<title>{title}</title>'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">'
            f'<style>{css}</style></head><body>{body}</body></html>')
