"""Watermark: a faint image centred behind the text on every PDF page.

The image is embedded as a data URI, so the HTML stays self-contained, and an
SVG stays a vector in the PDF. `position: fixed` makes Chrome repeat the
element on every printed page; it takes no space in the flow, so page breaks
and the one-page limit of the one-pager are unaffected. The watermark is part
of the PDF route only: DOCX and Markdown are handed on for editing and copy,
where a background image gets in the way.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .config import WATERMARK_TYPES, ConfigError, WatermarkSpec


def watermark_uri(path: Path) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ConfigError(f"watermark: cannot read {path}: {exc}") from None
    mime = WATERMARK_TYPES[Path(path).suffix.lower()]
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def watermark_html(spec: WatermarkSpec, uri: str) -> str:
    """A fixed, non-interactive layer under the content. `width` is a share
    of the page area; the empty alt keeps the image out of the text layer."""
    style = ("position:fixed;left:50%;top:50%;"
             f"width:{spec.width * 100:g}%;transform:translate(-50%,-50%);"
             f"opacity:{spec.opacity:g};z-index:-1;pointer-events:none")
    return (f'<div class="watermark" aria-hidden="true" style="{style}">'
            f'<img src="{uri}" alt="" style="display:block;width:100%;height:auto">'
            f'</div>')
