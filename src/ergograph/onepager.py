"""The one-pager: a landscape A4 page that shows at a glance what the person
can do, for recipients who will not read a CV (see SPEC R25).

It reuses the content file: contact, facts, certificates and languages
come from the same keys as the CV, and a reference project only names the
id of a project item and adds its short bullets. The one-pager's own
block (`onepager:`) holds what exists nowhere else: the summary, the key
figures, the competency clusters and the stations of the timeline.
"""

from __future__ import annotations

from .fragments import _link, contact_html, photo_html


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
            "description": entry.get("description"),
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
    return (f'<div class="op-head"><div class="op-head-row">'
            f'{photo_html(photo, name, "op-photo")}'
            f'<div class="op-id"><div class="name">{name}</div>'
            f'<div class="title">{content["title"]}</div>'
            f'<div class="op-summary">{summary}</div></div>{facts_html}</div>'
            # full width here, so a photo does not narrow it
            f'{contact_html(content)}</div>')


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
    legend = content["onepager"]["labels"].get("legend")
    if legend:
        out.append(f'<div class="op-legend">{legend}</div>')
    return "".join(out)


def _projects(content: dict) -> str:
    out = []
    for proj in reference_projects(content):
        top = f'<span class="ph">{proj["title"]}</span>'
        if proj["period"]:
            top += f'<span class="pp">{proj["period"]}</span>'
        sub = " · ".join(x for x in (proj["role"], proj["org"]) if x)
        sub_html = f'<div class="po">{sub}</div>' if sub else ""
        desc = f'<div class="pd">{proj["description"]}</div>' if proj["description"] else ""
        sub_html += desc
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
        rows = "".join(f'<div class="pub">{r}</div>' for r in box.get("items") or [])
        blocks.append(f'<h2 class="section">{box["title"]}</h2>{rows}')
    return "".join(blocks)


def _month(value, where: str) -> float:
    """'YYYY-MM' (or a bare year) as a fractional year."""
    text = str(value).strip()
    try:
        if "-" in text:
            year, month = text.split("-", 1)
            return int(year) + (int(month) - 1) / 12
        return float(int(text))
    except ValueError:
        raise ValueError(f"onepager.timeline: '{text}' is not YYYY-MM ({where})") from None


def timeline_tracks(stations: list[dict]) -> list[tuple[str, list[dict]]]:
    """Stations grouped by `track`, in the order the tracks first appear."""
    tracks: dict[str, list[dict]] = {}
    for st in stations:
        tracks.setdefault(str(st.get("track") or ""), []).append(st)
    return list(tracks.items())


def _stations(stations: list[dict]) -> str:
    items = "".join(
        f'<div class="st"><i></i><span class="sp">{s["period"]}</span>'
        f'<b>{s["label"]}</b>'
        + (f'<span class="ss">{s["sub"]}</span>' if s.get("sub") else "")
        + "</div>"
        for s in stations)
    return f'<div class="stations">{items}</div>'


def _gantt(stations: list[dict]) -> str:
    """Several tracks on one proportional time axis (every station has
    `from`, and `to` unless it is still running)."""
    spans = []
    for st in stations:
        start = _month(st["from"], st["label"])
        end = _month(st["to"], st["label"]) + 1 / 12 if st.get("to") else None
        spans.append((st, start, end))
    first = min(start for _, start, _ in spans)
    last = max(end or start for _, start, end in spans)
    lo = int(first)
    hi = int(last) + 1 + (1 if any(end is None for *_, end in spans) else 0)
    width = hi - lo

    def pct(value):
        return (value - lo) / width * 100

    ticks = "".join(
        f'<span class="tk" style="left:{pct(year):.2f}%">{year}</span>'
        for year in range(lo, hi + 1) if (year - lo) % 2 == 0)
    rows = [f'<div class="tr-label"></div><div class="tr-axis">{ticks}</div>']
    for track, items in timeline_tracks(stations):
        bars = []
        for st, start, end in ((s, a, b) for s, a, b in spans if s in items):
            left = pct(start)
            right = pct(end if end is not None else hi)
            open_cls = "" if end is not None else " open"
            text_pos = (f"right:{100 - right:.2f}%;text-align:right" if left > 72
                        else f"left:{left:.2f}%")
            text = (f'<b>{st["label"]}</b>'
                    + (f'<span class="ss">{st["sub"]}</span>' if st.get("sub") else "")
                    + f'<span class="sp">{st["period"]}</span>')
            bars.append(
                f'<i class="bar{open_cls}" style="left:{left:.2f}%;'
                f'width:{max(right - left, 0.8):.2f}%"></i>'
                f'<div class="bt" style="{text_pos}">{text}</div>')
        rows.append(f'<div class="tr-label">{track}</div>'
                    f'<div class="tr-lane">{"".join(bars)}</div>')
    return f'<div class="gantt">{"".join(rows)}</div>'


def _timeline(content: dict) -> str:
    stations = content["onepager"].get("timeline") or []
    if not stations:
        return ""
    lab = content["onepager"]["labels"]
    proportional = all(st.get("from") for st in stations)
    body = _gantt(stations) if proportional else _stations(stations)
    return (f'<div class="op-timeline"><h2 class="section">{lab["timeline"]}</h2>'
            f'{body}</div>')


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
