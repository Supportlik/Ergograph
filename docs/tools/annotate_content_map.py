"""Regenerate docs/images/content-keys.png — the annotated content-file map.

The image shows a real rendered CV with numbered boxes around the regions each
YAML key produces, so readers can see where their content ends up. It is built
from the committed example persona, so it contains no personal data.

Run it after theme or layout changes:

    cd examples/minimal && uv run ergograph build --html-only && cd ../..
    uv run --with pymupdf python docs/tools/annotate_content_map.py

PyMuPDF is only used here, to turn the rendered page into a PNG; it is not a
dependency of the package itself (see SPEC D9).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ergograph.pdf import find_chrome, render_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# The English rendering is used so the image reads for every visitor; page 1
# of the combined dossier is the CV part.
SOURCE = ROOT / "examples/minimal/.build/html/mit-stundensatz/en/dossier-complete.html"
TARGET = ROOT / "docs/images/content-keys.png"

#: One entry per annotated region:
#:   badge          the number shown in the legend
#:   outline        selector for every element that gets a dashed box
#:   anchor         selector for the single element the badge is pinned to
#:   side           which sheet edge the badge sits on
#:   kind           "content" (from content/<lang>.yaml) or "config" (config.yaml)
#: `labels` is cross-cutting — it produces every heading — so it gets its own
#: colour and a single badge on the first sidebar heading.
REGIONS = [
    ("1", ".header .title", ".header .title", "left", "content"),
    ("2", ".header .contact", ".header .contact", "left", "content"),
    ("3", ".profile", ".profile", "left", "content"),
    ("4", ".side .block:nth-of-type(1)", ".side .block:nth-of-type(1)", "left", "content"),
    ("5", ".side .block:nth-of-type(2)", ".side .block:nth-of-type(2)", "left", "content"),
    ("6", ".side .block:nth-of-type(3)", ".side .block:nth-of-type(3)", "left", "content"),
    ("7", ".side .block:nth-of-type(4)", ".side .block:nth-of-type(4)", "left", "content"),
    ("8", ".main .entry:not(:has(ul))", ".main h2:nth-of-type(1)", "right", "content"),
    ("9", ".main .edu", ".main h2:nth-of-type(2)", "right", "content"),
    ("10", ".main .entry:has(ul)", ".main h2:nth-of-type(3)", "right", "content"),
    ("11", "h2.section, .side .block h3", ".side .block:nth-of-type(1) h3", "gap", "labels"),
    ("A", ".header .name", ".header .name", "left", "config"),
]

COLORS = {"content": "#dc2626", "config": "#2563eb", "labels": "#047857"}
#: Badge offsets per edge; "gap" puts the badge into the column gutter.
OFFSETS = {"left": "left: -6.6mm", "right": "right: -6.6mm", "gap": "right: -17px"}


def annotation_css() -> str:
    rules = [
        "* { print-color-adjust: exact; -webkit-print-color-adjust: exact; }",
        # Room for the badges at both sheet edges.
        "body { padding: 0 7mm; }",
    ]
    for badge, outline, anchor, side, kind in REGIONS:
        color = COLORS[kind]
        style = "dotted" if kind == "labels" else "dashed"
        rules.append(f"{outline} {{ outline: 1.2px {style} {color}; "
                     f"outline-offset: 2px; }}")
        rules.append(f"{anchor} {{ position: relative; }}")
        rules.append(
            f'{anchor}::after {{ content: "{badge}"; position: absolute; '
            f"{OFFSETS[side]}; top: -1px; min-width: 11px; height: 11px; "
            f"padding: 0 1px; box-sizing: border-box; border-radius: 6px; "
            f"background: {color}; color: #fff; "
            f"font: 700 7.5px/11px Helvetica, sans-serif; text-align: center; }}")
    return "\n".join(rules)


def main() -> int:
    if not SOURCE.exists():
        print(f"missing {SOURCE}\nBuild the example first: "
              f"cd examples/minimal && uv run ergograph build --html-only",
              file=sys.stderr)
        return 1

    html = SOURCE.read_text(encoding="utf-8")
    marker = "</style>"
    if marker not in html:
        print("no </style> found in the rendered HTML", file=sys.stderr)
        return 1
    annotated = html.replace(marker, annotation_css() + marker, 1)

    import pymupdf

    with tempfile.TemporaryDirectory() as tmp:
        tmp_html = Path(tmp) / "annotated.html"
        tmp_html.write_text(annotated, encoding="utf-8")
        tmp_pdf = Path(tmp) / "annotated.pdf"
        if not render_pdf(find_chrome(None), tmp_html, tmp_pdf):
            print("Chrome did not produce a PDF", file=sys.stderr)
            return 1
        doc = pymupdf.open(tmp_pdf)
        page = doc[0]
        # Crop to the used area so the image is not half a blank A4 sheet.
        blocks = [b[:4] for b in page.get_text("blocks")]
        bottom = max((b[3] for b in blocks), default=page.rect.height)
        clip = pymupdf.Rect(0, 0, page.rect.width,
                            min(page.rect.height, bottom + 24))
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=140, clip=clip).save(TARGET)
        pages = doc.page_count
        doc.close()

    size = TARGET.stat().st_size
    print(f"wrote {TARGET.relative_to(ROOT)} ({size / 1024:.0f} kB, page 1 of {pages})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
