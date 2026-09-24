"""Small HTML fragments shared by the documents and the one-pager."""

from __future__ import annotations


def _link(value: str, url: str | None) -> str:
    return f'<a href="{url}">{value}</a>' if url else value


def breaks_before(contact: dict, photo: bool) -> bool:
    """`break_before: true` always starts a new line before the entry,
    `break_before: photo` only when a photo narrows the header."""
    flag = contact.get("break_before")
    return flag is True or (flag == "photo" and photo)


def contact_html(content: dict, photo: bool = False) -> str:
    parts = "".join(
        ('<span class="br"></span>' if breaks_before(c, photo) else "")
        + f'<span><b>{c["label"]}:</b> {_link(c["value"], c.get("url"))}</span>'
        for c in content["contact"])
    return f'<div class="contact">{parts}</div>' if parts else ""


def photo_html(photo, name: str, css_class: str = "photo") -> str:
    if photo is None:
        return ""
    return f'<img class="{css_class}" src="{photo.data_uri()}" alt="{name}">'
