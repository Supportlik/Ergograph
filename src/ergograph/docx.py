"""DOCX export: writes the four documents as Office Open XML.

The package is assembled from scratch with the standard library (`zipfile`
plus string templates) instead of a document library, so the dependency set
stays at PyYAML + pypdf (see D19). The emitted package is the minimal valid
WordprocessingML set: content types, the two relationship parts, document,
styles, a page-number footer and the core/app metadata.

The layout mirrors the `modern` theme (D21): same palette, same type scale,
the same two-column CV grid, right-aligned periods, pill-shaped skill tags, a
rule under every section heading and level bars next to the skill names. What
the CSS does with grid and flexbox is expressed here with borderless tables,
tab stops, paragraph borders and run shading. Every link the HTML sets is a
real Word hyperlink: contact values, certificate names and their verify link,
publication links and inline `<a>` inside any content value.

Content values are trusted HTML fragments (D2): `<br>` becomes a line break,
`<a href>` a hyperlink, `<b>`/`<strong>` and `<i>`/`<em>` toggle character
formatting, every other tag is dropped and its text kept.
"""

from __future__ import annotations

import struct
import zipfile
import zlib
from html import unescape
from html.parser import HTMLParser
from xml.sax.saxutils import escape, quoteattr

#: A4 and margins in twips (1/20 pt), taken from the theme's
#: `@page { size: A4; margin: 14mm 15mm }` — 14 mm top and bottom, 15 mm left
#: and right. Guessing 20 mm here cost 12 mm of height and 10 mm of width, and
#: the narrower column forced extra line wraps, which is what pushed the Word
#: version onto an additional page compared with the PDF.
_PAGE_W, _PAGE_H = 11906, 16838
_MARGIN_V = 794   # 14 mm
_MARGIN_H = 850   # 15 mm
#: Usable text width; every column width is derived from it.
_TEXT_W = _PAGE_W - 2 * _MARGIN_H
#: Line spacing. CSS `line-height: 1.5` means 1.5 x the *font size*, while
#: Word's "1.5 lines" means 1.5 x the font's own *line height*. Taking 1.5
#: (w:line="360") therefore produced lines far taller than the PDF and cost a
#: whole extra page. The arithmetic gives a starting point (240 * 1.5 divided
#: by the font's line-height factor), but the exact value is settled against
#: the PDF, because Segoe UI and the theme's Inter also differ in width and
#: that shifts where lines wrap. Measured: at 313 Word fitted about five
#: lines more per page than the PDF, which moved every break point.
_LINE = 347

#: `.cv-grid { grid-template-columns: 1fr 2.25fr; gap: 22px }`
_GAP = 330
_SIDE_W = int((_TEXT_W - _GAP) / 3.25)
_MAIN_W = _TEXT_W - _GAP - _SIDE_W
#: `.skills-cols { column-count: 2; column-gap: 7mm }` — the skills matrix is
#: typeset in two columns, which is why a single-column Word version came out
#: twice as tall and cost an extra page in the combined dossier.
_COL_GAP = 397   # 7 mm
_COL_W = (_TEXT_W - _COL_GAP) // 2

#: Type scale: the theme states sizes in CSS px and Chrome prints at 96 dpi,
#: so 1px = 0.75pt and a Word half-point value is round(px * 1.5). Getting
#: this wrong makes the Word file ~30 % larger than the PDF and everything
#: that relies on a line fitting (role plus right-aligned period) wraps.
#: The palette of themes/modern.css, as Word hex colours (no leading #).
INK = "0F172A"        # .name, .side h3, .entry .role
BODY = "334155"       # .entry li, .side .row .v
SOFT = "475569"       # .profile, .pub-summary
MUTED = "64748B"      # .period, .org meta, .pt
FAINT = "94A3B8"      # .side .row .k, .cert span, .skill .note
BLUE = "2563EB"       # .title, h2.section, .entry .org
LINK = "1D4ED8"       # .cert a, .proj .ph, .tag text
TAG_BG = "EFF6FF"     # .tag background
RULE = "E2E8F0"       # h2.section border, .skill .bar track
ACCENT = "DBEAFE"     # .proj left border

_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)

#: document.xml additionally carries the DrawingML namespaces, because the
#: skill level bars are inline pictures (see `_bar_png`).
_NS_DOC = _NS + (
    ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
    ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
    ' xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
    ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
    ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
    ' mc:Ignorable="wps"'
)

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Default Extension="jpeg" ContentType="image/jpeg"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _styles_xml(base_font: str) -> str:
    """Only document defaults; every other property is set on the run itself,
    so the result does not depend on Word's built-in style definitions."""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:styles {_NS}><w:docDefaults><w:rPrDefault><w:rPr>'
            f'<w:rFonts w:ascii={quoteattr(base_font)} w:hAnsi={quoteattr(base_font)} '
            f'w:cs={quoteattr(base_font)}/>'
            f'<w:sz w:val="20"/><w:szCs w:val="20"/><w:color w:val="{BODY}"/>'
            '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
            f'<w:spacing w:after="60" w:line="{_LINE}" w:lineRule="auto"/>'
            '</w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/></w:style></w:styles>')


def _footer_run(text: str) -> str:
    return (f'<w:r><w:rPr><w:sz w:val="15"/><w:color w:val="{FAINT}"/></w:rPr>'
            f'<w:t xml:space="preserve">{text}</w:t></w:r>')


_FOOTER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:ftr {_NS}><w:p><w:pPr><w:jc w:val="center"/>'
           f'<w:rPr><w:sz w:val="15"/><w:color w:val="{FAINT}"/></w:rPr></w:pPr>'
           '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
           '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
           '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
           + _footer_run("1") +
           '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
           + _footer_run(" / ") +
           '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
           '<w:r><w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r>'
           '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
           + _footer_run("1") +
           '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
           '</w:p></w:ftr>')


# --------------------------------------------------------------------------
# HTML fragment -> runs
# --------------------------------------------------------------------------

class _FragmentParser(HTMLParser):
    """Split a trusted HTML fragment into (text, bold, italic, href) runs.

    `<br>` yields a run whose text is None, which the writer turns into a
    Word line break. Unknown tags are transparent: their text is kept.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[tuple[str | None, bool, bool, str | None]] = []
        self._bold = 0
        self._italic = 0
        self._href: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.runs.append((None, False, False, None))
        elif tag in ("b", "strong"):
            self._bold += 1
        elif tag in ("i", "em"):
            self._italic += 1
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href.append(href)

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.runs.append((None, False, False, None))

    def handle_endtag(self, tag):
        if tag in ("b", "strong"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("i", "em"):
            self._italic = max(0, self._italic - 1)
        elif tag == "a" and self._href:
            self._href.pop()

    def handle_data(self, data):
        if data:
            self.runs.append((data, self._bold > 0, self._italic > 0,
                              self._href[-1] if self._href else None))


def fragment_runs(value) -> list[tuple[str | None, bool, bool, str | None]]:
    """Parse a content value into runs. Non-strings are stringified first."""
    parser = _FragmentParser()
    parser.feed(str(value))
    parser.close()
    return parser.runs


class _Rels:
    """Collects the relationships of one document: external hyperlinks and
    the embedded images of the skill level bars."""

    def __init__(self) -> None:
        self._items: list[tuple[str, str]] = []
        self.media: dict[str, bytes] = {}
        self._by_bytes: dict[bytes, str] = {}
        self._drawings = 0

    def hyperlink(self, target: str) -> str:
        rid = f"hId{len(self._items) + 1}"
        self._items.append((rid, target))
        return rid

    def image(self, data: bytes, extension: str = "png") -> str:
        """Add an image part and return its relationship id. Identical bytes
        are stored once: the bars repeat, there are only a handful of
        distinct (width, level) pairs per document."""
        rid = self._by_bytes.get(data)
        if rid is None:
            name = f"image{len(self.media) + 1}.{extension}"
            self.media[name] = data
            rid = f"mId{len(self.media)}"
            self._by_bytes[data] = rid
        return rid

    def next_drawing_id(self) -> int:
        """wp:docPr ids have to be unique within the document."""
        self._drawings += 1
        return self._drawings

    def xml(self) -> str:
        links = "".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/hyperlink" Target={quoteattr(target)} '
            f'TargetMode="External"/>'
            for rid, target in self._items)
        images = "".join(
            f'<Relationship Id="{self._by_bytes[data]}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/image" Target="media/{name}"/>'
            for name, data in self.media.items())
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
                f'{links}{images}</Relationships>')


# --------------------------------------------------------------------------
# Level bars as inline pictures
# --------------------------------------------------------------------------

#: EMU per CSS pixel at the 96 dpi Chrome prints with (914400 / 96).
_EMU_PX = 9525
#: Device pixels per CSS pixel in the generated bar bitmaps. Four is enough
#: for the rounded caps to look clean at print resolution and keeps the part
#: a few hundred bytes.
_BAR_SCALE = 4
#: `.skill .bar { height: 6px; border-radius: 4px }` — with a 6px box the
#: browser clamps the radius to half the height, so the bar is a stadium.
_BAR_H = 6.0
_BAR_R = _BAR_H / 2
#: `linear-gradient(90deg,#3b82f6,#2563eb)` across the filled part.
_BAR_FROM = (0x3B, 0x82, 0xF6)
_BAR_TO = (0x25, 0x63, 0xEB)
_BAR_TRACK = (0xE2, 0xE8, 0xF0)


def _png(width: int, height: int, pixels: bytes) -> bytes:
    """Minimal RGBA PNG. `pixels` is width*height*4 bytes, row major."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)                       # filter type 0 (None)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def _stadium_coverage(x: float, y: float, width: float) -> float:
    """Antialiased coverage of the rounded bar at CSS point (x, y): the set of
    points no further than the radius from the horizontal centre segment."""
    if width <= 0:
        return 0.0
    radius = min(_BAR_R, width / 2)
    cx = min(max(x, radius), max(width - radius, radius))
    dx, dy = x - cx, y - _BAR_R
    distance = (dx * dx + dy * dy) ** 0.5 - radius
    return min(1.0, max(0.0, 0.5 - distance * _BAR_SCALE))


def _bar_png(width_px: float, ratio: float) -> bytes:
    """The `.skill .bar` of the theme as a bitmap: an #e2e8f0 stadium with a
    blue gradient stadium of `ratio` of its width on top.

    Word has no rounded rectangle in the text flow and the previous stand-in,
    a run of shaded spaces, was both square-ended and far too short (a space
    at 5pt is about a quarter of its own height wide, so 22 of them came out
    at a third of the width the CSS grid gives the bar). A picture is the one
    form Word and Word for the web both place at an exact size.
    """
    dev_w = max(1, int(round(width_px * _BAR_SCALE)))
    dev_h = int(round(_BAR_H * _BAR_SCALE))
    fill_w = width_px * min(max(ratio, 0.0), 1.0)
    out = bytearray(dev_w * dev_h * 4)
    for py in range(dev_h):
        y = (py + 0.5) / _BAR_SCALE
        for px in range(dev_w):
            x = (px + 0.5) / _BAR_SCALE
            track = _stadium_coverage(x, y, width_px)
            if track <= 0:
                continue
            fill = _stadium_coverage(x, y, fill_w)
            if fill > 0:
                t = min(1.0, x / width_px) if width_px else 0.0
                blue = tuple(round(a + (b - a) * t)
                             for a, b in zip(_BAR_FROM, _BAR_TO))
            else:
                blue = _BAR_FROM
            rest = max(0.0, track - fill)
            offset = (py * dev_w + px) * 4
            for channel in range(3):
                mixed = (blue[channel] * fill + _BAR_TRACK[channel] * rest) / track
                out[offset + channel] = min(255, max(0, round(mixed)))
            out[offset + 3] = round(track * 255)
    return _png(dev_w, dev_h, bytes(out))


def _bar(rels: _Rels, width_twips: int, level: float, level_max: float) -> str:
    """An inline picture run holding one level bar `width_twips` wide."""
    width_px = width_twips / 15          # twips -> pt -> px at 96 dpi
    data = _bar_png(width_px, level / level_max if level_max else 0.0)
    rid = rels.image(data)
    ident = rels.next_drawing_id()
    cx, cy = round(width_px * _EMU_PX), round(_BAR_H * _EMU_PX)
    return (
        # w:position (half-points) lifts the bar off the baseline so it sits
        # level with the middle of the name rather than on its baseline,
        # which is what `align-items: center` does. The baselines themselves
        # already match, because the bar's line is set to the same exact
        # height as the name's (see `_SKILL_LINE`).
        '<w:r><w:rPr><w:noProof/><w:position w:val="2"/></w:rPr><w:drawing>'
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{ident}" name="Level {level:g}"/>'
        '<wp:cNvGraphicFramePr>'
        '<a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
        'drawingml/2006/picture"><pic:pic>'
        f'<pic:nvPicPr><pic:cNvPr id="{ident}" name="bar.png"/>'
        '<pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/>'
        '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')


def _rpr(*, bold=False, italic=False, size=15, color=BODY, caps=False,
         spacing=0, shade=None, underline=False) -> str:
    parts = []
    if bold:
        parts.append("<w:b/>")
    if italic:
        parts.append("<w:i/>")
    if caps:
        parts.append("<w:caps/>")
    if spacing:
        parts.append(f'<w:spacing w:val="{spacing}"/>')
    if shade:
        parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    if underline:
        parts.append('<w:u w:val="single"/>')
    parts.append(f'<w:color w:val="{color}"/>')
    parts.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def _run(text: str, **fmt) -> str:
    return (f"<w:r>{_rpr(**fmt)}"
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')


def _tab(**fmt) -> str:
    return f"<w:r>{_rpr(**fmt)}<w:tab/></w:r>"


#: U+2060 WORD JOINER. No period carries one today — with `.entry .role` at
#: its proper size they all fit beside their role — but `extract_text` still
#: strips it, so a future nowrap fix cannot leak into the text layer or the
#: ATS comparison.
_JOINER = "\u2060"


def _frag(value, rels: _Rels, *, link_color=LINK, **fmt) -> str:
    """Render a content value (trusted HTML fragment) as runs, turning every
    `<a href>` into a real Word hyperlink."""
    out = []
    base_color = fmt.pop("color", BODY)
    for text, bold, italic, href in fragment_runs(value):
        if text is None:
            out.append("<w:r><w:br/></w:r>")
            continue
        local = dict(fmt)
        local["bold"] = fmt.get("bold", False) or bold
        local["italic"] = fmt.get("italic", False) or italic
        local["color"] = link_color if href else base_color
        run = _run(text, **local)
        out.append(f'<w:hyperlink r:id="{rels.hyperlink(href)}">{run}</w:hyperlink>'
                   if href else run)
    return "".join(out)


def _ppr(*, before=0, after=60, indent=0, hanging=0, indent_right=0,
         right_tab=None, tab_at=None, border_bottom=None, border_left=None,
         keep_next=False, keep_lines=False, line=_LINE,
         line_rule="auto", mark_size=None) -> str:
    # schema order inside w:pPr: keepNext, keepLines, pageBreakBefore,
    # widowControl, pBdr, tabs, spacing, ind, rPr, sectPr
    parts = []
    if keep_next:
        parts.append("<w:keepNext/>")
    if keep_lines:
        parts.append("<w:keepLines/>")
    parts.append("<w:widowControl/>")
    borders = ""
    if border_bottom:
        color, sz = border_bottom
        borders += (f'<w:bottom w:val="single" w:sz="{sz}" w:space="3" '
                    f'w:color="{color}"/>')
    if border_left:
        color, sz = border_left
        borders += (f'<w:left w:val="single" w:sz="{sz}" w:space="8" '
                    f'w:color="{color}"/>')
    if borders:
        parts.append(f"<w:pBdr>{borders}</w:pBdr>")
    if indent or hanging or indent_right:
        parts.append(f'<w:ind w:left="{indent}" w:right="{indent_right}" '
                     f'w:hanging="{hanging}"/>')
    if right_tab or tab_at:
        stops = ""
        if tab_at:
            stops += f'<w:tab w:val="left" w:pos="{tab_at}"/>'
        if right_tab:
            stops += f'<w:tab w:val="right" w:pos="{right_tab}"/>'
        parts.append(f"<w:tabs>{stops}</w:tabs>")
    parts.append(f'<w:spacing w:before="{before}" w:after="{after}" '
                 f'w:line="{line}" w:lineRule="{line_rule}"/>')
    if mark_size:
        # The paragraph mark takes part in the line height. Setting it makes
        # a line as tall as one of text at that size even when the line holds
        # nothing but a picture — which is how the level bar ends up on the
        # same baseline as the skill name in the cell beside it.
        parts.append(f'<w:rPr><w:sz w:val="{mark_size}"/>'
                     f'<w:szCs w:val="{mark_size}"/></w:rPr>')
    return f"<w:pPr>{''.join(parts)}</w:pPr>"


def _p(runs: str, **pfmt) -> str:  # noqa: D401
    return f"<w:p>{_ppr(**pfmt)}{runs}</w:p>"


# --------------------------------------------------------------------------
# Recurring building blocks
# --------------------------------------------------------------------------

def _section_heading(text: str, rels: _Rels) -> str:
    """`h2.section`: blue, uppercase, letter-spaced, hairline underneath."""
    return _p(_frag(text, rels, bold=True, size=16, color=BLUE, caps=True,
                    spacing=26),
              before=180, after=90, border_bottom=(RULE, 4), keep_next=True)


def _side_heading(text: str, rels: _Rels) -> str:
    """`.side h3`: dark, uppercase, no rule."""
    return _p(_frag(text, rels, bold=True, size=15, color=INK, caps=True,
                    spacing=20), before=150, after=60, keep_next=True,
              line=_SIDE_HEAD_LINE, line_rule="exact")


def _period_room(period) -> int:
    """Twips to keep free at the right edge for a right-aligned period.

    `.entry .period { white-space: nowrap }` sits in a flex row, so the text
    beside it wraps *before* it and the period stays on the first line. A
    right tab stop alone does not do that: the text runs the full width and
    the period is then broken in the middle ("11/2019-" / "03/2020"). Giving
    the paragraph a right indent of the period's own width reserves the
    space, and the tab stop beyond that indent puts the period into it.
    """
    return round(_text_width(str(period), 6.5) * 15) + 150


def _bullet(runs: str, *, indent=284, right_tab=None, period=None) -> str:
    # w:pos is measured from the left margin, so the stop is the same
    # absolute position for indented and non-indented paragraphs.
    return _p(_run("•  ", size=15, color=BODY) + runs,
              indent=indent, hanging=170, after=50, right_tab=right_tab,
              indent_right=_period_room(period) if period else 0)


def _cell(width: int, content: str, *, valign: str | None = None,
          vmerge: str | None = None) -> str:
    """One table cell. `vmerge` is "restart" for the first cell of a vertical
    merge and "continue" for the ones below it. w:tcPr children are order
    sensitive: tcW, then vMerge, then vAlign."""
    merge = ""
    if vmerge == "restart":
        merge = '<w:vMerge w:val="restart"/>'
    elif vmerge == "continue":
        merge = "<w:vMerge/>"
    va = f'<w:vAlign w:val="{valign}"/>' if valign else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{merge}{va}</w:tcPr>'
            f'{content}</w:tc>')


def _table(rows: list[list[tuple[int, str]]], *, right_margin=0) -> str:
    """A borderless fixed-layout table spanning the full text width."""
    widths = [w for w, _ in rows[0]]
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    total = sum(widths)
    # Width in dxa together with a fixed layout is the combination Word itself
    # emits. Declaring the width in percent *and* asking for a fixed layout is
    # contradictory and made Word refuse to break the row across pages.
    props = (f'<w:tblPr><w:tblW w:w="{total}" w:type="dxa"/>'
             '<w:tblLayout w:type="fixed"/>'
             '<w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
             '<w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
             f'<w:right w:w="{right_margin}" w:type="dxa"/></w:tblCellMar>'
             '</w:tblPr>')
    # No w:cantSplit element at all: its absence is the "may break across
    # pages" default, while writing <w:cantSplit w:val="false"/> is risky
    # because a reader that only checks for the element's presence would read
    # it as "keep together" and push the whole row to the next page.
    body = "".join(
        "<w:tr>" + "".join(_cell(w, c) for w, c in row) + "</w:tr>"
        for row in rows)
    return f"<w:tbl>{props}<w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>"


#: Usable height of one page: A4 minus the two margins.
_PAGE_TEXT_H = _PAGE_H - 2 * _MARGIN_V
#: Safety margin on the first grid row. `_estimate_height` is a rough
#: model and the reading view is unforgiving: a row one line too tall
#: does not break, it moves to the next page and leaves the rest of
#: this one empty.
_ROW_RESERVE = 1400   # about 25 mm
#: The CSS arithmetic alone lands about a tenth tighter than the PDF: Word
#: measures a line from the font's metrics, the browser adds the half-leading
#: on top of a slightly different ascent, and Segoe UI is not Inter. Measured
#: on the English CV, where the tenth is the difference between the BAMF
#: position opening page 2, as in the PDF, and being pulled onto page 1.
_LINE_TRIM = 1.10

#: Exact line heights for the header and the sidebar, taken straight from
#: the CSS (`line-height: 1.5` is 1.5 x the font size, 1px = 15 twips). The
#: `_LINE` multiple applies to the *font's* line height instead and comes
#: out about a quarter taller; over a header and a full sidebar that adds
#: some 45 mm, which is exactly the room the first page was missing for the
#: last block of the main column.
_NAME_LINE = 608       # .header .name, 27px
_TITLE_LINE = 281      # .header .title, 12.5px
_CONTACT_LINE = 198    # .header .contact, 8.8px
_PROFILE_LINE = 225    # .profile, 10px
_SIDE_HEAD_LINE = 214  # .side h3, 9.5px
_SIDE_ROW_LINE = 203   # .side .row, 9px
_SIDE_KEY_LINE = 176   # .side .row .k, 7.8px
_CERT_SUB_LINE = 180   # .cert span, 8px
_TAG_LINE = 189        # .tag, 8.4px


def _estimate_height(block: str, width: int) -> int:
    """Roughly how tall `block` will be in twips when set `width` twips wide.

    Only used to decide how much of the main column fits beside the sidebar
    in the CV grid's first row, so it has to be in the right ballpark, not
    exact. Every paragraph contributes its spacing plus as many lines as its
    text needs at the paragraph's own font size and indents.
    """
    import re

    total = 0
    for par in re.findall(r"<w:p>.*?</w:p>", block, re.S):
        props = par[:par.index("</w:pPr>") + 8] if "</w:pPr>" in par else ""
        def attr(pattern, default=0):
            found = re.search(pattern, props)
            return int(found.group(1)) if found else default
        before = attr(r'w:before="(-?\d+)"')
        after = attr(r'w:after="(-?\d+)"', 60)
        line = attr(r'w:line="(\d+)"', _LINE)
        exact = 'w:lineRule="exact"' in props
        left = attr(r'<w:ind w:left="(-?\d+)"')
        right = attr(r'w:right="(-?\d+)"')
        sizes = [int(v) for v in re.findall(r'<w:sz w:val="(\d+)"/>', par)]
        half_pt = max(sizes) if sizes else 20
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", par, re.S))
        usable = max(300, width - left - right)
        columns = _text_width(text, half_pt / 2) * 15      # px -> twips
        lines = max(1, -(-int(columns) // usable))
        # a multiple applies to the font's own line height (about 1.33 em)
        height = line if exact else round(half_pt * 10 * 1.33 * line / 240)
        total += before + after + lines * height
    return total


#: EMU per twip (914400 / 1440).
_EMU_TWIP = 635


def _indent_block(block: str, delta: int) -> str:
    """Shift every paragraph of `block` right by `delta` twips.

    The CV's main column is indented past the sidebar instead of sitting in
    a table cell, so the indent has to be added to what each paragraph
    already carries (bullets bring their own).
    """
    import re

    def bump(match):
        return f'<w:ind w:left="{int(match.group(1)) + delta}"'

    block = re.sub(r'<w:ind w:left="(-?\d+)"', bump, block)
    out, pos = [], 0
    for match in re.finditer(r"<w:pPr>(.*?)</w:pPr>", block, re.S):
        props = match.group(1)
        out.append(block[pos:match.start()])
        if "<w:ind " not in props:
            # schema order: w:ind goes after pBdr and before tabs/spacing
            anchor = "<w:tabs>" if "<w:tabs>" in props else "<w:spacing "
            props = props.replace(
                anchor, f'<w:ind w:left="{delta}"/>{anchor}', 1)
        out.append(f"<w:pPr>{props}</w:pPr>")
        pos = match.end()
    out.append(block[pos:])
    return "".join(out)


def _text_frame(content: str, width: int, height: int, ident: int) -> str:
    """The sidebar as an anchored text frame, floating left of the main
    column and taking no part in the text flow.

    A table would be the obvious shape for a two-column CV, and it was the
    one used until now, but the reading view of Word for the web moves a
    table to a fresh page as soon as anything precedes it, whatever its
    height — the same file paginates correctly in the editing view. Without
    a table the CV is ordinary flowing text and both renderers agree with
    the PDF. The trade-off is that some ATS parsers skip text inside a
    frame; the sidebar carries availability, languages and certificates.
    """
    cx, cy = width * _EMU_TWIP, height * _EMU_TWIP
    return (
        '<w:r><w:rPr><w:noProof/></w:rPr><w:drawing>'
        '<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0"'
        ' relativeHeight="251658240" behindDoc="0" locked="0"'
        ' layoutInCell="1" allowOverlap="1">'
        '<wp:simplePos x="0" y="0"/>'
        '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset>'
        '</wp:positionH>'
        '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset>'
        '</wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{ident}" name="Sidebar"/>'
        '<wp:cNvGraphicFramePr/>'
        '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/'
        'word/2010/wordprocessingShape"><wps:wsp>'
        '<wps:cNvSpPr txBox="1"/>'
        f'<wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/>'
        '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '<a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr>'
        f'<wps:txbx><w:txbxContent>{content}</w:txbxContent></wps:txbx>'
        '<wps:bodyPr rot="0" spcFirstLastPara="0" vertOverflow="overflow"'
        ' horzOverflow="overflow" vert="horz" wrap="square" lIns="0" tIns="0"'
        ' rIns="0" bIns="0" anchor="t" anchorCtr="0"><a:spAutoFit/>'
        '</wps:bodyPr></wps:wsp></a:graphicData></a:graphic>'
        '</wp:anchor></w:drawing></w:r>')


def _table_separator() -> str:
    """A hairline paragraph between two adjacent tables.

    OOXML needs a paragraph there, otherwise Word merges the two tables into
    one. A normal empty paragraph costs a full line each, and with one per
    skill category that added about ten lines and pushed the skills part of
    the combined dossier onto a second page. Setting the paragraph mark to
    1 pt with an exact line height makes the separator effectively invisible.
    """
    # w:vanish on the paragraph mark: hidden text takes no space at all, so
    # the separator cannot push anything onto a further page. At 1 pt it
    # still did — the combined dossier ended on a seventh, empty page,
    # because the two-column matrix fills its page to the last line.
    return ('<w:p><w:pPr><w:widowControl/>'
            '<w:spacing w:before="0" w:after="0" w:line="20" '
            'w:lineRule="exact"/><w:rPr><w:vanish/><w:sz w:val="2"/>'
            '<w:szCs w:val="2"/></w:rPr></w:pPr></w:p>')


def _sect_pr(*, cols: int = 1, break_type: str | None = None) -> str:
    """Section properties. `cols=2` is the Word equivalent of the theme's
    `column-count: 2` on the skills matrix. Child order is fixed by the
    schema: footerReference, type, pgSz, pgMar, cols."""
    kind = f'<w:type w:val="{break_type}"/>' if break_type else ""
    columns = (f'<w:cols w:num="2" w:space="{_COL_GAP}" w:equalWidth="1"/>'
               if cols == 2 else '<w:cols w:space="708"/>')
    return ('<w:sectPr><w:footerReference w:type="default" r:id="rId2"/>'
            f'{kind}<w:pgSz w:w="{_PAGE_W}" w:h="{_PAGE_H}"/>'
            f'<w:pgMar w:top="{_MARGIN_V}" w:right="{_MARGIN_H}" '
            f'w:bottom="{_MARGIN_V}" w:left="{_MARGIN_H}" '
            f'w:header="454" w:footer="454" w:gutter="0"/>'
            f'{columns}</w:sectPr>')


def _section_break() -> str:
    """A paragraph that closes the single-column section before the skills
    matrix. In OOXML the properties of a section sit in the last paragraph of
    that section, so this paragraph carries the one-column settings."""
    # w:sectPr is the second to last child of w:pPr, after w:rPr — the schema
    # fixes that order and Word rejects a document that gets it wrong.
    return ('<w:p><w:pPr><w:widowControl/>'
            '<w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>'
            '<w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr>'
            f'{_sect_pr(cols=1)}'
            '</w:pPr></w:p>')


def _page_break() -> str:
    """`page-break-before: always` as a property of the following paragraph.

    A paragraph of its own holding only a page break would leave an empty
    line at the top of the new page, which the CSS does not, and in the
    combined dossier that line is taken off the one page the skills matrix
    has to fit on.
    """
    return "<!--pageBreakBefore-->"


def _link_value(entry: dict) -> str:
    url = entry.get("url")
    return f'<a href="{url}">{entry["value"]}</a>' if url else entry["value"]


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------

#: `.header .photo { width: 25mm }` and the 16px flex gap beside it.
_PHOTO_W = 1417
_PHOTO_GAP = 240


def _photo_anchor(photo, rels: _Rels, width: int, height: int, name: str) -> str:
    """The photo as a picture anchored to the top right corner of the text
    area, outside the text flow, with rounded corners like the theme's
    `border-radius: 2.5mm`. The file is embedded unchanged (see photo.py)."""
    rid = rels.image(photo.data, photo.extension)
    ident = rels.next_drawing_id()
    cx, cy = width * _EMU_TWIP, height * _EMU_TWIP
    return (
        '<w:r><w:rPr><w:noProof/></w:rPr><w:drawing>'
        '<wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0"'
        ' relativeHeight="251659264" behindDoc="0" locked="0"'
        ' layoutInCell="1" allowOverlap="1">'
        '<wp:simplePos x="0" y="0"/>'
        '<wp:positionH relativeFrom="margin"><wp:align>right</wp:align>'
        '</wp:positionH>'
        '<wp:positionV relativeFrom="margin"><wp:posOffset>0</wp:posOffset>'
        '</wp:positionV>'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
        f'<wp:docPr id="{ident}" name="Photo" descr={quoteattr(name)}/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/>'
        '</wp:cNvGraphicFramePr>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
        'drawingml/2006/picture"><pic:pic>'
        f'<pic:nvPicPr><pic:cNvPr id="{ident}" name="photo.{photo.extension}"'
        f' descr={quoteattr(name)}/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/>'
        '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 10000"/>'
        '</a:avLst></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')


def _header_blocks(name: str, content: dict, rels: _Rels, photo=None) -> str:
    """Name, title and the inline contact row, closed by the thick blue rule
    of `.header { border-bottom: 3px solid #2563eb }`.

    With a photo, name and title keep clear of it by a right indent and move
    down so that they end level with the photo's lower edge, as
    `align-items: flex-end` does in the theme; the contact row follows at
    full width below both."""
    right = _PHOTO_W + _PHOTO_GAP if photo is not None else 0
    row = []
    for index, contact in enumerate(content["contact"]):
        if index:
            row.append(_run("     ", size=13, color=MUTED))
        row.append(_run(f'{contact["label"]}: ', bold=True, size=13, color=BODY))
        row.append(_frag(_link_value(contact), rels, size=13, color=MUTED,
                         link_color=BLUE))
    rule = {"border_bottom": (BLUE, 18)}
    title_fmt = dict(after=90, line=_TITLE_LINE, line_rule="exact",
                     indent_right=right)
    contact_par = ""
    if row:
        # full width even beside a photo: the photo ends above this row
        contact_par = _p("".join(row), after=170, **rule, line=_CONTACT_LINE,
                         line_rule="exact")
    else:
        title_fmt.update(after=170, **rule)
    before = 0
    anchor = ""
    if photo is not None:
        height = round(_PHOTO_W * photo.ratio)
        text = _NAME_LINE + 20 + _TITLE_LINE + 90
        before = max(0, height - text)
        anchor = _photo_anchor(photo, rels, _PHOTO_W, height, name)
    out = [_p(anchor + _run(name, bold=True, size=40, color=INK, spacing=-6),
              before=before, after=20, line=_NAME_LINE, line_rule="exact",
              indent_right=right),
           _p(_frag(content["title"], rels, bold=True, size=19, color=BLUE),
              **title_fmt),
           contact_par]
    return "".join(out)


# --------------------------------------------------------------------------
# CV: sidebar + main, as a two-column grid
# --------------------------------------------------------------------------

#: `.tag { padding: 2px 7px; font-size: 8.4px; border-radius: 4px }` in a
#: `.tags { display: flex; flex-wrap: wrap; gap: 4px }`. In Word a pill is a
#: shaded run, and run shading always fills the *line*, so the line has to be
#: the pill: its height is the pill's height and the 4px gap between rows is
#: the paragraph spacing, not part of the line. That means the rows cannot be
#: left to the layout engine — one paragraph per row, wrapped here.
_PILL_LINE = 210       # 14px: 8.4px text at 1.5 plus 2px padding either side
_PILL_GAP = 60         # 4px between rows
_PILL_PAD = "\u00a0\u00a0\u00a0"   # about 7px of inner padding at 6.5pt


def _pills(skills: list) -> str:
    """The core-competency tags, one paragraph per row of pills."""
    rows, current, used = [], [], 0.0
    limit = _SIDE_W / 15                      # twips -> CSS px
    for skill in skills:
        label = str(skill)
        # _text_width is tuned for body text and runs a few per cent wide on
        # the pills' semibold face; measured against the PDF, where "DevOps ·
        # CI/CD" and "Requirements Engineering" still share the last row.
        width = _text_width(label, 6.5) * 0.95 + 14      # 7px padding each side
        if current:
            width += 4                                   # .tags { gap: 4px }
        if current and used + width > limit:
            rows.append(current)
            current, used = [], 0.0
            width -= 4
        current.append(label)
        used += width
    if current:
        rows.append(current)

    out = []
    for index, row in enumerate(rows):
        runs = []
        for position, label in enumerate(row):
            if position:
                # `.tags { gap: 4px }` — two spaces at 6.5pt are about that;
                # three were noticeably wider than the PDF and pushed the last
                # pill of a row onto a line of its own
                runs.append(_run("  ", size=13))
            # A pill is a shaded run, not a rounded shape: a shape carries its
            # own text box, and the sidebar is already one — Word refuses to
            # open a document with a text box inside a text box ("Word ran
            # into a problem opening this document"). So the corners stay
            # square; everything else about the pill is the theme's.
            # A plain space inside a label would be a break opportunity and
            # would split the pill along with its shading, so inside a pill
            # every space is non-breaking.
            text = label.replace(" ", "\u00a0")
            runs.append(_run(f"{_PILL_PAD}{text}{_PILL_PAD}", bold=True,
                             size=13, color=LINK, shade=TAG_BG))
        last = index == len(rows) - 1
        out.append(_p("".join(runs), after=110 if last else _PILL_GAP,
                      line=_PILL_LINE, line_rule="exact"))
    return "".join(out)


def _sidebar(content: dict, rels: _Rels) -> str:
    lab = content["labels"]
    out = []
    if content["facts"]:
        out.append(_side_heading(lab["facts"], rels))
        for fact in content["facts"]:
            out.append(_p(_frag(fact["label"], rels, size=11, color=FAINT,
                                caps=True, spacing=10), after=0,
                          line=_SIDE_KEY_LINE, line_rule="exact"))
            out.append(_p(_frag(fact["value"], rels, bold=True, size=13,
                                color=BODY), after=80,
                          line=_SIDE_ROW_LINE, line_rule="exact"))
    if content["languages"]:
        out.append(_side_heading(lab["languages"], rels))
        for entry in content["languages"]:
            out.append(_p(_frag(entry["name"], rels, bold=True, size=13, color=BODY)
                          + _run("  ", size=13)
                          + _frag(entry["level"], rels, size=13, color=MUTED),
                          after=50, line=_SIDE_ROW_LINE, line_rule="exact"))
    if content["certs"]:
        out.append(_side_heading(lab["certs"], rels))
        for cert in content["certs"]:
            url = cert.get("url")
            name = f'<a href="{url}">{cert["name"]}</a>' if url else cert["name"]
            out.append(_p(_frag(name, rels, bold=True, size=13, color=INK),
                          after=0, line=_SIDE_ROW_LINE, line_rule="exact"))
            if cert.get("description"):
                out.append(_p(_frag(cert["description"], rels, size=12,
                                    color=FAINT), after=0,
                              line=_CERT_SUB_LINE, line_rule="exact"))
            if url:
                out.append(_p(_frag(f'<a href="{url}">↗ {lab["verify"]}</a>',
                                    rels, size=11, link_color=BLUE), after=80,
                              line=_CERT_SUB_LINE, line_rule="exact"))
    if content["top_skills"]:
        out.append(_side_heading(lab["core"], rels))
        # `.tag`: pill-shaped; Word has no border radius, so a pill is a
        # shaded run. The inner padding uses non-breaking spaces, otherwise
        # Word drops them at a line break and the shading touches the label;
        # the gap between two pills is a wider unshaded run, so neighbouring
        # pills stay visually separate instead of merging into one band.
        out.append(_pills(content["top_skills"]))
    return "".join(out)


def _keep_together(paragraphs: list[str]) -> str:
    """Bind a run of paragraphs so a renderer keeps them on one page.

    This is `break-inside: avoid` for a block: every paragraph but the last
    gets w:keepNext. Word only honours it between paragraphs, which is why
    the CV and the skills matrix are built from paragraphs rather than table
    rows (see D26, D27).
    """
    import re

    out = []
    for index, par in enumerate(paragraphs):
        last = index == len(paragraphs) - 1
        if not last and "<w:keepNext/>" not in par:
            par = re.sub(r"<w:pPr>", "<w:pPr><w:keepNext/>", par, count=1)
        out.append(par)
    return "".join(out)


def _experience_chunks(content: dict, rels: _Rels, right: int) -> list[str]:
    """One block per position, so no grid row grows taller than a page."""
    chunks = []
    for entry in content["experience"]:
        out = []
        # `.entry .role { font-size: 11.2px }` -> round(11.2 * 1.5) = 17 half
        # points. It stood at 22 (11 pt), a third too large, which is also
        # why the period no longer fitted on the line beside a long role.
        out.append(_p(_frag(entry["role"], rels, bold=True, size=17, color=INK)
                      + _tab()
                      + _frag(entry["period"], rels, bold=True, size=13,
                              color=MUTED),
                      before=150, after=0, right_tab=right, keep_next=True,
                      indent_right=_period_room(entry["period"])))
        # bound to the first bullet as well: without this the role and its
        # employer stay behind alone at the foot of a page while the bullets
        # move on, and the break lands elsewhere than in the PDF (observed
        # with the BAMF position)
        out.append(_p(_frag(entry["org"], rels, bold=True, size=15, color=BLUE),
                      after=70, keep_next=True))
        for bullet in entry["bullets"]:
            if isinstance(bullet, dict):
                runs = _frag(bullet["text"], rels, size=15, color=BODY)
                if bullet.get("period"):
                    runs += _tab() + _frag(bullet["period"], rels, bold=True,
                                           size=13, color=MUTED)
                out.append(_bullet(runs, right_tab=right,
                                   period=bullet.get("period")))
                if bullet.get("org"):
                    out.append(_p(_frag(bullet["org"], rels, size=13, color=MUTED),
                                  indent=454, after=50, keep_lines=True))
            else:
                out.append(_bullet(_frag(bullet, rels, size=15, color=BODY)))
        # `.entry { break-inside: avoid }`: a position moves to the next page
        # as a whole rather than being torn in half, which is also what keeps
        # the break points the same as in the PDF. keepNext on every
        # paragraph but the last is the Word equivalent.
        chunks.append(_keep_together(out))
    return chunks


def _education(content: dict, rels: _Rels) -> str:
    """`.edu`: blue year in a narrow column, degree and institution beside it."""
    out = []
    for entry in content["education"]:
        out.append(_p(_frag(entry["year"], rels, bold=True, size=13, color=BLUE)
                      + _run("   ", size=13)
                      + _frag(entry["degree"], rels, bold=True, size=15, color=INK),
                      after=0, keep_next=True))
        out.append(_p(_frag(entry["institution"], rels, size=13, color=MUTED),
                      indent=624, after=80, keep_lines=True))
    return "".join(out)


def _publications(content: dict, rels: _Rels) -> str:
    lab = content["labels"]
    out = []
    for pub in content["publications"]:
        runs = _frag(f'{pub["title"]}.', rels, bold=True, size=15, color=INK)
        runs += _frag(f' {pub["venue"]}.', rels, size=15, color=BODY)
        if pub.get("url"):
            runs += _run(" ", size=15)
            runs += _frag(f'<a href="{pub["url"]}">↗ {lab["link"]}</a>', rels,
                          size=13, link_color=BLUE)
        out.append(_bullet(runs))
        if pub.get("summary"):
            out.append(_p(_frag(pub["summary"], rels, size=15, color=SOFT),
                          indent=454, after=80, keep_lines=True))
    return "".join(out)


def _cv_blocks(content: dict, rels: _Rels, head: str = "") -> str:
    """Header and profile across the full width, then the main column as
    flowing text indented past the sidebar, with the sidebar itself in an
    anchored frame beside it (see `_text_frame`)."""
    lab = content["labels"]
    out = [head, _p(_frag(content["tagline"], rels, size=15, color=SOFT),
                    after=150, line=_PROFILE_LINE, line_rule="exact")]

    # right tab stops are measured from the left margin, so they stay at the
    # text edge even though the paragraphs are indented
    experience = _experience_chunks(content, rels, _TEXT_W - 60)
    main = [_section_heading(lab["experience"], rels)]
    main += experience
    main.append(_section_heading(lab["education"], rels)
                + _education(content, rels))
    if content["publications"]:
        main.append(_section_heading(lab["publications"], rels)
                    + _publications(content, rels))
    body = _indent_block("".join(main), _SIDE_W + _GAP)

    side = _sidebar(content, rels)
    if side:
        frame = _text_frame(side, _SIDE_W,
                            _estimate_height(side, _SIDE_W),
                            rels.next_drawing_id())
        # the frame is anchored in the first paragraph of the main column,
        # so it starts level with it
        body = body.replace("<w:p>", "<w:p>", 1)
        cut = body.index("</w:pPr>") + len("</w:pPr>")
        body = body[:cut] + frame + body[cut:]
    out.append(body)
    return "".join(out)


# --------------------------------------------------------------------------
# Project history
# --------------------------------------------------------------------------

def _paragraphs(description) -> list:
    return [description] if isinstance(description, str) else list(description)


def _projects_blocks(content: dict, rels: _Rels) -> str:
    lab = content["labels"]
    right = _TEXT_W - 60
    # `.proj { border-left: 2px solid #dbeafe; padding-left: 10px }`
    edge = {"border_left": (ACCENT, 12), "indent": 200}
    out = [_section_heading(lab["projects"], rels)]
    for group in content["projects"]:
        out.append(_p(_frag(group["group"], rels, bold=True, size=16, color=INK),
                      before=170, after=0, keep_next=True))
        out.append(_p(_frag(group["meta"], rels, size=13, color=MUTED),
                      after=120, keep_next=True))
        for item in group["items"]:
            head = _frag(item["title"], rels, bold=True, size=16, color=LINK)
            room = _period_room(item["period"]) if item.get("period") else 0
            if item.get("period"):
                head += _tab() + _frag(item["period"], rels, bold=True, size=13,
                                       color=MUTED)
            out.append(_p(head, before=100, after=0, right_tab=right,
                          indent_right=room,
                          keep_next=True, **edge))
            if item.get("org"):
                out.append(_p(_frag(item["org"], rels, bold=True, size=13,
                                    color=MUTED), after=40, **edge))
            for para in _paragraphs(item["description"]):
                text = str(para).strip()
                if text.startswith("•"):
                    out.append(_p(_run("•  ", size=15, color=BODY)
                                  + _frag(text.lstrip("• ").strip(), rels,
                                          size=15, color=BODY),
                                  indent=484, hanging=170, after=40,
                                  border_left=(ACCENT, 12)))
                else:
                    out.append(_p(_frag(text, rels, size=15, color=BODY),
                                  after=60, keep_next=True, **edge))
            out.append(_p(_frag(item["tech"], rels, size=13, color=MUTED),
                          after=120, **edge))
    return "".join(out)


# --------------------------------------------------------------------------
# Skills matrix
# --------------------------------------------------------------------------

#: `.skill { grid-template-columns: 140px 1fr auto; gap: 8px }` in twips
#: (1px = 15 twips): the name column, the gap on either side of the bar and
#: the `.lvl { min-width: 22px }` column the level sits in. The bar is what
#: is left over, which is the `1fr`.
_SKILL_NAME_W = 2100   # 140px
_SKILL_GAP = 120       # 8px
_SKILL_LVL_W = 330     # 22px
#: Line heights in the matrix, stated exactly instead of as a multiple.
#: Everywhere else `_LINE` as a multiple is fine, but here it is not: the bar
#: sits on a line of its own in the neighbouring cell, and unless that line
#: is exactly as tall as the name's the two baselines drift apart and the bar
#: lands across the note. The values are `_LINE` resolved for the sizes used
#: here (_LINE/240 x the font's line height, about 1.33 em in Segoe UI), so
#: the matrix keeps the height it was calibrated to — taking the CSS
#: arithmetic instead (1.5 x the font size) makes it a quarter shorter and
#: the standalone matrix collapses from two pages to one.
_SKILL_LINE = 230      # 7pt name
_NOTE_LINE = 198       # 6pt note
_CAT_LINE = 230        # 7pt category heading


#: Rough advance widths for Segoe UI Semibold, as a fraction of the font
#: size. Only used to decide whether a skill name fits the 140px column, so
#: a few per cent either way does not matter; the classes are narrow (i l j
#: t f r punctuation), wide (m w M W) and everything else.
_NARROW = set("ijlt.,:;!|'()[]/ ")
_WIDE = set("mwMW@%")


def _text_width(text: str, size_pt: float) -> float:
    """Approximate width of `text` in CSS pixels at `size_pt` points."""
    units = 0.0
    for char in text:
        if char in _NARROW:
            units += 0.32
        elif char in _WIDE:
            units += 0.90
        elif char.isupper() or char.isdigit():
            units += 0.62
        else:
            units += 0.54
    return units * size_pt / 0.75      # pt -> CSS px at 96 dpi


def _wrap_name(name: str, width_px: float, size_pt: float) -> list[str]:
    """Break a skill name into the lines the 140px CSS column would give it.

    The name column is a tab stop, not a cell, so Word cannot wrap it: a name
    that does not fit pushes past the stop and drags the bar and the level
    out of the grid with it ("Microservices & Cloud-Architekturen"). Breaking
    it here, at the same place the CSS column would, keeps the grid intact.
    """
    words = str(name).split(" ")
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and _text_width(candidate, size_pt) > width_px:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _skill_lines(cat: dict, level_max: float, rels: _Rels, width: int) -> str:
    """One category as plain paragraphs: the heading, then per skill a line
    `name <tab> bar <tab> level` with the note underneath.

    Paragraphs rather than a table, because `.skill-cat { break-inside:
    avoid }` has no equivalent for table rows — neither cantSplit nor
    keepNext binds across them in Word for the web, so a column break tore
    notes off their skill and left categories half in one column and half in
    the other. Between paragraphs keepNext does bind, and chaining every
    paragraph of a category but the last is exactly `break-inside: avoid`.
    Long names are wrapped by `_wrap_name` instead of by the layout engine.
    """
    out = [_p(_frag(cat["category"], rels, bold=True, size=14, color=INK,
                    caps=True, spacing=16),
              before=120, after=60, keep_next=True, line=_CAT_LINE,
              line_rule="exact")]
    bar_at = _SKILL_NAME_W + _SKILL_GAP
    bar_w = width - bar_at - _SKILL_GAP - _SKILL_LVL_W
    items = list(cat["items"])
    for index, item in enumerate(items):
        level = float(item["level"])
        note = item.get("note")
        last = index == len(items) - 1
        lines = _wrap_name(item["name"], _SKILL_NAME_W / 15, 7)
        # every line of the name but the last is a paragraph of its own; the
        # bar sits on the last one, which is where `align-items: center`
        # puts it for a two-line name
        for text in lines[:-1]:
            out.append(_p(_frag(text, rels, bold=True, size=14, color=BODY),
                          after=0, keep_next=True, line=_SKILL_LINE,
                          line_rule="exact"))
        # the right stop sits 2px inside the column: on the edge itself Word
        # treats a wider level ("5.5") as an overflow and wraps it to its own
        # line, while a narrow one ("4") still fits
        out.append(_p(_frag(lines[-1], rels, bold=True, size=14, color=BODY)
                      + _tab()
                      + _bar(rels, bar_w, level, level_max)
                      + _tab()
                      + _run(f"{level:g}", bold=True, size=12, color=MUTED),
                      after=0 if note else 38, right_tab=width - 30,
                      tab_at=bar_at, keep_next=not last or note is not None,
                      line=_SKILL_LINE, line_rule="exact"))
        if note:
            out.append(_p(_frag(note, rels, size=12, color=FAINT),
                          after=38, keep_next=not last, line=_NOTE_LINE,
                          line_rule="exact"))
    return "".join(out)



def _skills_blocks(content: dict, level_max: float, rels: _Rels) -> str:
    """The skills matrix, laid out exactly as the theme does it.

    In the HTML the heading and the legend sit *outside* `.skills-cols`, so
    they run the full text width and only the categories are flowed down the
    left column and on into the right one by `column-count: 2`. Word models
    that with two sections: the heading and the legend end the one-column
    one, then a *continuous* section break opens a `w:cols w:num="2"`
    section that the categories flow through.

    The earlier stand-in, a borderless two-column table with the first half
    of the categories left and the second half right, does not reproduce the
    flow: it pairs categories row by row, so the wrong ones end up next to
    each other and a short category leaves a gap its neighbour cannot use.
    """
    lab = content["labels"]
    out = [_section_heading(lab["skills"], rels),
           _p(_frag(lab["legend"], rels, size=12, color=FAINT), after=110),
           _section_break()]
    for cat in content["skills"]:
        out.append(_skill_lines(cat, level_max, rels, _COL_W))
    return "".join(out)


# --------------------------------------------------------------------------
# Package assembly
# --------------------------------------------------------------------------

def document_body(name: str, content: dict, level_max: float, document: str,
                  rels: _Rels, photo=None) -> str:
    """Body blocks for one canonical document key (cv/projects/skills/full)."""
    header = _header_blocks(name, content, rels, photo)
    parts = {"cv": ["cv"], "projects": ["projects"], "skills": ["skills"],
             "full": ["cv", "projects", "skills"]}[document]
    # the CV emits the header itself, right above its indented main column
    blocks = [] if parts[0] == "cv" else [header]
    for index, part in enumerate(parts):
        if index:
            blocks.append(_page_break())   # folded into the next paragraph
        if part == "cv":
            blocks.append(_cv_blocks(content, rels, header))
        elif part == "projects":
            blocks.append(_projects_blocks(content, rels))
        else:
            blocks.append(_skills_blocks(content, level_max, rels))
    return "".join(blocks)


def _exact_line_heights(document_xml: str) -> str:
    """Give every paragraph the line height the theme gives it.

    The theme sets `line-height: 1.5` once, on `body`, and CSS multiplies
    that by the *font size*. Word's multiple (`w:lineRule="auto"`) multiplies
    the *font's own line height* instead, about 1.33 em in Segoe UI, so the
    same number comes out a quarter taller — over a whole CV that is a page.
    Calibrating the multiple against one document only moves the error
    around, so each paragraph gets `w:lineRule="exact"` at 1.5 x its largest
    font size. Paragraphs that already state an exact height keep it: those
    are the ones tuned to something other than the text they hold, such as
    the skill rows, whose height has to match the bar picture beside them.
    """
    import re

    def fix(match):
        par = match.group(0)
        if 'w:lineRule="auto"' not in par:
            return par
        sizes = [int(v) for v in re.findall(r'<w:sz w:val="(\d+)"/>', par)]
        half_pt = max(sizes) if sizes else 20
        line = round(half_pt / 2 * 1.5 * 20 * _LINE_TRIM)
        return re.sub(r'w:line="\d+" w:lineRule="auto"',
                      f'w:line="{line}" w:lineRule="exact"', par)

    return re.sub(r"<w:p>.*?</w:p>", fix, document_xml, flags=re.S)


def _core_xml(title: str, author: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:title>{escape(title)}</dc:title>'
            f'<dc:creator>{escape(author)}</dc:creator>'
            f'<cp:lastModifiedBy>{escape(author)}</cp:lastModifiedBy>'
            '</cp:coreProperties>')


_APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
            'extended-properties">'
            '<Application>Ergograph</Application></Properties>')


def build_docx(path, name: str, content: dict, level_max: float, document: str,
               *, title: str, lang: str = "de",
               base_font: str = "Segoe UI", photo=None,
               author: str | None = None) -> None:
    """Write one document as a .docx package to `path`.

    `title` goes into the package metadata only; the visible content is
    identical to the HTML/PDF route for the same `document` key.
    """
    rels = _Rels()
    body = document_body(name, content, level_max, document, rels, photo)
    if body.rstrip().endswith("</w:tbl>"):
        # OOXML forbids a body that ends in a table. A normal empty paragraph
        # there costs a full line, and where the last page is full that line
        # alone opens another page (it did, on the standalone CV). The
        # hairline separator is the same paragraph at 1 pt.
        body += _table_separator()
    # The two-column section is the last one, so how it starts is stated in
    # the body-level sectPr, and it always starts *continuous*: the matrix
    # follows its own heading on the same page, in the dossier as much as
    # standalone (the dossier opens that page with a plain page break).
    # Leaving the type out is not neutral — OOXML then defaults to nextPage,
    # which is what used to push the matrix onto a page of its own.
    # "continuous" throughout: as the type of the *last* section it also
    # keeps Word from opening an empty page after the final table, which a
    # one-part document (the CV) ended on.
    sect = _sect_pr(cols=2 if document in ("full", "skills") else 1,
                    break_type="continuous")
    # fold every page break marker into the w:pPr of the paragraph after it
    for lead in ("<w:keepNext/><w:keepLines/>", "<w:keepNext/>",
                 "<w:keepLines/>", ""):
        body = body.replace(f"<!--pageBreakBefore--><w:p><w:pPr>{lead}",
                            f"<w:p><w:pPr>{lead}<w:pageBreakBefore/>")
    assert "<!--pageBreakBefore-->" not in body, "page break lost its paragraph"
    document_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    f'<w:document {_NS_DOC}><w:body>{body}{sect}</w:body></w:document>')
    # Pin the font on every run. Word honours w:docDefaults, but simpler
    # readers (macOS Quick Look, some ATS parsers) only look at the run and
    # would otherwise fall back to a serif face. w:rFonts has to come first
    # inside w:rPr, which is exactly where this inserts it.
    document_xml = document_xml.replace(
        "<w:rPr>", f'<w:rPr><w:rFonts w:ascii={quoteattr(base_font)} '
                   f'w:hAnsi={quoteattr(base_font)} w:cs={quoteattr(base_font)}/>')
    document_xml = _exact_line_heights(document_xml)
    parts = {
        "[Content_Types].xml": _CONTENT_TYPES,
        "_rels/.rels": _ROOT_RELS,
        "docProps/core.xml": _core_xml(title, name if author is None else author),
        "docProps/app.xml": _APP_XML,
        "word/_rels/document.xml.rels": rels.xml(),
        "word/document.xml": document_xml,
        "word/styles.xml": _styles_xml(base_font),
        "word/footer1.xml": _FOOTER,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml must be the first entry of an OPC package.
        for part, data in parts.items():
            zf.writestr(part, data)
        for name, blob in rels.media.items():
            # already deflated, storing keeps the package honest about size
            zf.writestr(f"word/media/{name}", blob, zipfile.ZIP_STORED)


# --------------------------------------------------------------------------
# Text extraction (the DOCX counterpart of pdf.extract_text)
# --------------------------------------------------------------------------

class _TextParser(HTMLParser):
    """Pulls the visible text out of a word/document.xml.

    Runs inside one paragraph are concatenated without a separator (a word
    may be split across runs); `<w:br/>`, `<w:tab/>`, paragraph and table
    cell ends contribute a space, mirroring how `ats.plain_text` flattens
    `<br>` in the source values. Field instructions (PAGE, NUMPAGES) are
    skipped so they cannot leak into the comparison.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._in_text = 0
        self._in_instr = 0

    def handle_starttag(self, tag, attrs):
        if tag == "w:t":
            self._in_text += 1
        elif tag == "w:instrtext":
            self._in_instr += 1
        elif tag in ("w:br", "w:tab", "w:cr"):
            self.out.append(" ")

    def handle_startendtag(self, tag, attrs):
        if tag in ("w:br", "w:tab", "w:cr"):
            self.out.append(" ")

    def handle_endtag(self, tag):
        if tag == "w:t":
            self._in_text = max(0, self._in_text - 1)
        elif tag == "w:instrtext":
            self._in_instr = max(0, self._in_instr - 1)
        elif tag in ("w:p", "w:tc"):
            self.out.append(" ")

    def handle_data(self, data):
        if self._in_text and not self._in_instr:
            self.out.append(data)


def extract_text(path) -> str | None:
    """Return the text layer of a .docx, or None if it cannot be read."""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError):
        return None
    parser = _TextParser()
    parser.feed(xml)
    parser.close()
    text = unescape("".join(parser.out)).replace(_JOINER, "")
    # pills pad and join their labels with non-breaking spaces
    return text.replace("\u00a0", " ")
