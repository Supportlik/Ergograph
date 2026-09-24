"""The one-pager: a landscape A4 page that shows at a glance what the person
can do, for recipients who will not read a CV (see SPEC R25).

It reuses the content file: contact, facts, certificates and languages
come from the same keys as the CV, and a reference project only names the
id of a project item and adds its short bullets. The one-pager's own
block (`onepager:`) holds what exists nowhere else: the summary, the key
figures, the competency clusters and the stations of the timeline.
"""

from __future__ import annotations

from .render import _link, contact_html, photo_html


def find_project(content: dict, ref: str) -> tuple[dict, dict]:
    """Return (group, item) of the project item with id `ref`."""
    for group in content["projects"]:
        for item in group["items"]:
            if item.get("id") == ref:
                return group, item
    raise KeyError(ref)


def reference_projects(content: dict) -> list[dict]:
    """The one-pager's project entries with their references resolved:
    every field falls back to the referenced project item."""
    out = []
    for entry in content["onepager"].get("projects") or []:
        item = {}
        if entry.get("ref"):
            _, item = find_project(content, entry["ref"])
        out.append({
            "title": entry.get("title") or item.get("title"),
            "period": entry.get("period", item.get("period")),
            "org": entry.get("org", item.get("org")),
            "role": entry.get("role"),
            "bullets": list(entry.get("bullets") or []),
            "tech": entry.get("tech", item.get("tech")),
        })
    return out


def onepager_facts(content: dict) -> list[dict]:
    """The facts shown on the one-pager: all of them, or only the labels
    listed in `onepager.facts`, in that order."""
    wanted = content["onepager"].get("facts")
    if not wanted:
        return list(content["facts"])
    by_label = {f["label"]: f for f in content["facts"]}
    return [by_label[label] for label in wanted if label in by_label]


def _level_bar(level: float, level_max: float) -> str:
    pct = round(float(level) / level_max * 100)
    return (f'<span class="bar"><i style="width:{pct}%"></i></span>'
            f'<span class="lvl">{float(level):g}</span>')


def _head(name: str, content: dict, photo) -> str:
    block = content["onepager"]
    lab = content["labels"]
    summary = block.get("summary") or content["tagline"]
    facts = "".join(
        f'<div class="row"><span class="k">{f["label"]}</span>'
        f'<span class="v">{f["value"]}</span></div>'
        for f in onepager_facts(content))
    facts_html = (f'<div class="op-facts"><h3>{lab["facts"]}</h3>{facts}</div>'
                  if facts else "")
    return (f'<div class="op-head">{photo_html(photo, name, "op-photo")}'
            f'<div class="op-id"><div class="name">{name}</div>'
            f'<div class="title">{content["title"]}</div>'
            f'<div class="op-summary">{summary}</div>'
            f'{contact_html(content)}</div>{facts_html}</div>')


def _highlights(content: dict) -> str:
    items = "".join(
        f'<div class="hl"><b>{h["value"]}</b><span>{h["label"]}</span></div>'
        for h in content["onepager"].get("highlights") or [])
    return f'<div class="op-highlights">{items}</div>' if items else ""


def _competencies(content: dict, level_max: float) -> str:
    out = []
    for cluster in content["onepager"].get("competencies") or []:
        top = f'<span class="cn">{cluster["name"]}</span>'
        if cluster.get("level") is not None:
            top += _level_bar(cluster["level"], level_max)
        tags = "".join(f'<span class="tag">{t}</span>'
                       for t in cluster.get("items") or [])
        out.append(f'<div class="cl"><div class="cl-top">{top}</div>'
                   f'<div class="tags">{tags}</div></div>')
    return "".join(out)


def _projects(content: dict) -> str:
    out = []
    for proj in reference_projects(content):
        top = f'<span class="ph">{proj["title"]}</span>'
        if proj["period"]:
            top += f'<span class="pp">{proj["period"]}</span>'
        sub = " · ".join(x for x in (proj["role"], proj["org"]) if x)
        sub_html = f'<div class="po">{sub}</div>' if sub else ""
        bullets = "".join(f"<li>{b}</li>" for b in proj["bullets"])
        ul = f"<ul>{bullets}</ul>" if bullets else ""
        tech = f'<div class="pt">{proj["tech"]}</div>' if proj["tech"] else ""
        out.append(f'<div class="op-proj"><div class="proj-top">{top}</div>'
                   f'{sub_html}{ul}{tech}</div>')
    return "".join(out)


def _side(content: dict) -> str:
    lab = content["labels"]
    blocks = []
    if content["certs"]:
        certs = "".join(
            f'<div class="cert"><b>{_link(c["name"], c.get("url"))}</b>'
            + (f'<span>{c["description"]}</span>' if c.get("description") else "")
            + "</div>"
            for c in content["certs"])
        blocks.append(f'<h2 class="section">{lab["certs"]}</h2>{certs}')
    if content["languages"]:
        langs = "".join(
            f'<div class="row"><span class="v">{lang["name"]}</span> '
            f'<span class="lv">{lang["level"]}</span></div>'
            for lang in content["languages"])
        blocks.append(f'<h2 class="section">{lab["languages"]}</h2>{langs}')
    extra = content["onepager"].get("extra") or []
    for box in extra:
        rows = "".join(f'<div class="row">{r}</div>' for r in box.get("items") or [])
        blocks.append(f'<h2 class="section">{box["title"]}</h2>{rows}')
    return "".join(blocks)


def _timeline(content: dict) -> str:
    stations = content["onepager"].get("timeline") or []
    if not stations:
        return ""
    lab = content["onepager"]["labels"]
    items = "".join(
        f'<div class="st"><i></i><span class="sp">{s["period"]}</span>'
        f'<b>{s["label"]}</b>'
        + (f'<span class="ss">{s["sub"]}</span>' if s.get("sub") else "")
        + "</div>"
        for s in stations)
    return (f'<div class="op-timeline"><h2 class="section">{lab["timeline"]}</h2>'
            f'<div class="stations">{items}</div></div>')


def onepager_html(name: str, content: dict, level_max: float, photo=None) -> str:
    lab = content["onepager"]["labels"]
    return (f'<div class="onepager">{_head(name, content, photo)}'
            f'{_highlights(content)}'
            f'<div class="op-cols">'
            f'<div class="op-col"><h2 class="section">{lab["competencies"]}</h2>'
            f'{_competencies(content, level_max)}</div>'
            f'<div class="op-col"><h2 class="section">{lab["projects"]}</h2>'
            f'{_projects(content)}</div>'
            f'<div class="op-col op-side">{_side(content)}</div>'
            f'</div>{_timeline(content)}</div>')
