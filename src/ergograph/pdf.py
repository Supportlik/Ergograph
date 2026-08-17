"""PDF generation via Chrome headless plus optional page numbers (PyMuPDF)."""

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

    Requires PyMuPDF (extra `pagenumbers`); without it, returns None and
    the check is skipped.
    """
    try:
        import fitz
    except ImportError:
        return None
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def finalize_pdf(pdf_path: Path, title: str | None = None,
                 author: str | None = None) -> bool:
    """Post-process a rendered PDF: page numbers and document metadata.

    Inserts a subtle page number 'i / n' at the bottom center and sets the
    PDF title/author metadata (helps ATS parsers and recruiters identify
    the document). Requires PyMuPDF (extra `pagenumbers`); without PyMuPDF
    the PDF stays unchanged and the function reports False.
    """
    try:
        import fitz
    except ImportError:
        return False
    doc = fitz.open(pdf_path)
    total = doc.page_count
    for i, page in enumerate(doc, 1):
        text = f"{i} / {total}"
        tw = fitz.get_text_length(text, fontname="helv", fontsize=8)
        x = (page.rect.width - tw) / 2
        y = page.rect.height - 16
        page.insert_text((x, y), text, fontname="helv", fontsize=8,
                         color=(0.5, 0.55, 0.62))
    metadata = doc.metadata or {}
    if title:
        metadata["title"] = title
    if author:
        metadata["author"] = author
    metadata["creator"] = "ergograph"
    doc.set_metadata(metadata)
    doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    return True
