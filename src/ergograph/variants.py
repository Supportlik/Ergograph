"""Variant resolution: reducing a content tree to what one variant shows.

Three mechanisms, all declarative and all resolved before rendering, so
the renderers never see a variant:

* List entries (mappings) may carry `variants: [...]` (keep only when one
  of the tags is active) and/or `except_variants: [...]` (drop when one of
  them is active). This works in every list of the content file, not only
  in `facts`.
* Any value may be written as `{by_variant: {<tag>: value, ..., default:
  value}}`; the first key whose tag is active wins, `default` otherwise.
* An anonymous variant removes the contact block and every link, and puts
  `anonymous_name` in place of the person's name (see `anonymize`).

A variant's tags are its own name plus the `tags` from the config, plus
`anonymous` for anonymous variants.
"""

from __future__ import annotations

import re

from .config import ConfigError

_FILTER_KEYS = ("variants", "except_variants")


def _keep(entry: dict, tags: frozenset[str]) -> bool:
    only = entry.get("variants")
    if only and not tags.intersection(str(t) for t in only):
        return False
    never = entry.get("except_variants")
    if never and tags.intersection(str(t) for t in never):
        return False
    return True


def resolve(value, tags: frozenset[str], where: str = "content"):
    """Return `value` with all variant constructs resolved for `tags`."""
    if isinstance(value, dict):
        if set(value) == {"by_variant"}:
            options = value["by_variant"]
            if not isinstance(options, dict):
                raise ConfigError(f"{where}: by_variant expects a mapping")
            for key, option in options.items():
                if key != "default" and str(key) in tags:
                    return resolve(option, tags, where)
            if "default" not in options:
                raise ConfigError(
                    f"{where}: by_variant has no entry for the active variant "
                    f"({', '.join(sorted(tags))}) and no 'default'")
            return resolve(options["default"], tags, where)
        return {k: resolve(v, tags, f"{where}.{k}")
                for k, v in value.items() if k not in _FILTER_KEYS}
    if isinstance(value, list):
        return [resolve(v, tags, f"{where}[{i}]") for i, v in enumerate(value)
                if not (isinstance(v, dict) and not _keep(v, tags))]
    return value


_LINK_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)


def _unlink(value):
    """Drop every `url` field and unwrap every inline <a> to its text: a
    link target (a Credly badge, a DOI, a profile URL) identifies the
    person as reliably as the name does."""
    if isinstance(value, dict):
        return {k: _unlink(v) for k, v in value.items() if k != "url"}
    if isinstance(value, list):
        return [_unlink(v) for v in value]
    if isinstance(value, str):
        return _LINK_RE.sub(r"\1", value)
    return value


def _replace(value, pairs: list[tuple[str, str]]):
    if isinstance(value, dict):
        return {k: _replace(v, pairs) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace(v, pairs) for v in value]
    if isinstance(value, str):
        for old, new in pairs:
            value = value.replace(old, new)
    return value


def anonymize(content: dict, where: str) -> tuple[str, dict]:
    """Return (display name, content) for an anonymous variant.

    Besides the name, contact block and links, `anonymous_replace` (a
    mapping text -> replacement) generalizes whatever else identifies the
    person, typically employers, internal system names and places. The
    longest key is replaced first, so "Universität Regensburg" can map to
    something else than "Regensburg" alone.
    """
    name = content.get("anonymous_name")
    if not name:
        raise ConfigError(f"{where}: an anonymous variant needs 'anonymous_name'")
    replace = content.get("anonymous_replace") or {}
    if not isinstance(replace, dict):
        raise ConfigError(f"{where}: anonymous_replace expects a mapping")
    pairs = sorted(((str(k), str(v)) for k, v in replace.items()),
                   key=lambda kv: len(kv[0]), reverse=True)
    body = {k: v for k, v in content.items() if k != "anonymous_replace"}
    out = _replace(_unlink(dict(body, contact=[])), pairs)
    return str(name), out


def identity_markers(name: str, content: dict) -> list[str]:
    """Strings that must not appear in an anonymous document: the full name,
    every part of it longer than two letters, every contact value and every
    key of `anonymous_replace`."""
    markers = [name, *(part for part in name.split() if len(part) > 2)]
    markers += [str(k) for k in (content.get("anonymous_replace") or {})]
    for contact in content.get("contact") or []:
        value = str(contact.get("value") or "").strip()
        if value:
            markers.append(value)
    return markers
