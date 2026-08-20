"""PDF generation via Chrome headless, plus page numbers and metadata (pypdf)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_chrome(configured: str | None = None) -> str:
    """Find Chrome/Chromium: config value > environment variable > known paths > PATH."""
    candidates = [configured, os.environ.get("ERGOGRAPH_CHROME"), *CHROME_CANDIDATES]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError(
        "Chrome/Chromium not found. Set the path in the config.yaml under "
        "'chrome:' or via the ERGOGRAPH_CHROME environment variable.")


def render_pdf(chrome: str, html_path: Path, pdf_path: Path) -> bool:
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=12000", "--run-all-compositor-stages-before-draw",
         "--no-pdf-header-footer",
         f"--print-to-pdf={pdf_path}", str(html_path)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return pdf_path.exists() and pdf_path.stat().st_size > 0


def extract_text(pdf_path: Path) -> str | None:
    """Extract the text layer of a PDF (for the ATS readability check).

    Returns None only if pypdf is missing, which happens exclusively in
    deliberately stripped installs (`pip install --no-deps`); the check is
    then skipped instead of failing the build.
    """
    try:
        import pypdf
    except ImportError:
        return None
    reader = pypdf.PdfReader(pdf_path)
    return "\n".join(page.extract_text() for page in reader.pages)


#: Helvetica advance widths per 1000 units of em, for the only characters a
#: page-number stamp can contain. Helvetica is one of the PDF base-14 fonts,
#: so it needs no embedding and no font file to measure against.
_STAMP_WIDTHS = {**{str(d): 556 for d in range(10)}, " ": 278, "/": 278}

_STAMP_SIZE = 8
_STAMP_BASELINE = 16
_STAMP_COLOR = "0.5 0.55 0.62"


def finalize_pdf(pdf_path: Path, title: str | None = None,
                 author: str | None = None) -> bool:
    """Post-process a rendered PDF: page numbers and document metadata.

    Inserts a subtle page number 'i / n' at the bottom center and sets the
    PDF title/author metadata (helps ATS parsers and recruiters identify
    the document). Returns False if pypdf is missing, leaving the PDF
    unchanged.
    """
    try:
        import pypdf
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    except ImportError:
        return False

    writer = pypdf.PdfWriter(clone_from=pypdf.PdfReader(pdf_path))
    total = len(writer.pages)
    helvetica = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    for number, page in enumerate(writer.pages, 1):
        text = f"{number} / {total}"
        width = sum(_STAMP_WIDTHS[c] for c in text) / 1000 * _STAMP_SIZE
        box = page.mediabox
        x = float(box.left) + (float(box.width) - width) / 2
        y = float(box.bottom) + _STAMP_BASELINE

        fonts = page.setdefault(NameObject("/Resources"), DictionaryObject()) \
                    .setdefault(NameObject("/Font"), DictionaryObject())
        fonts[NameObject("/ErgoHelv")] = helvetica

        contents = page.get_contents()
        body = contents.get_data() if contents is not None else b""
        stamped = DecodedStreamObject()
        # The page content is wrapped in q/Q before the stamp is appended:
        # Chrome emits a global `cm` transformation with no enclosing q, which
        # would otherwise scale and mirror the stamp along with the page.
        stamped.set_data(
            b"q\n" + body + b"\nQ\n"
            + f"q BT /ErgoHelv {_STAMP_SIZE} Tf {_STAMP_COLOR} rg "
              f"1 0 0 1 {x:.2f} {y:.2f} Tm ({text}) Tj ET Q\n".encode("ascii"))
        page.replace_contents(stamped)
        page.compress_content_streams()

    metadata = {"/Creator": "ergograph"}
    if title:
        metadata["/Title"] = title
    if author:
        metadata["/Author"] = author
    writer.add_metadata(metadata)
    with open(pdf_path, "wb") as fh:
        writer.write(fh)
    return True
