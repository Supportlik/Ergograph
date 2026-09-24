"""Orchestration: load config + content, write HTML, render PDFs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .ats import key_strings, missing_strings
from .config import Config, filter_facts, load_content
from .docx import build_docx
from .docx import extract_text as extract_docx_text
from .pdf import extract_text, finalize_pdf, find_chrome, render_pdf
from .render import build_documents, load_theme, page


@dataclass
class BuildResult:
    variant: str
    lang: str
    document: str
    html_path: Path
    pdf_path: Path | None
    ok: bool
    #: Key strings missing from the PDF text layer (ATS readability check);
    #: empty if everything was found or the check could not run (no pypdf).
    ats_missing: list[str] = field(default_factory=list)
    docx_path: Path | None = None
    #: Key strings missing from the DOCX text layer. The DOCX is generated
    #: from the same content, so anything listed here is a real defect.
    docx_ats_missing: list[str] = field(default_factory=list)


def output_filename(slug: str, doc_name: str, lang: str, datestamp: str | None,
                    suffix: str) -> str:
    prefix = f"{datestamp}_" if datestamp else ""
    return f"{prefix}{slug}_{doc_name}_{lang}.{suffix}"


def pdf_filename(slug: str, doc_name: str, lang: str, datestamp: str | None) -> str:
    return output_filename(slug, doc_name, lang, datestamp, "pdf")


def docx_filename(slug: str, doc_name: str, lang: str, datestamp: str | None) -> str:
    return output_filename(slug, doc_name, lang, datestamp, "docx")


def build(cfg: Config, *, variants: list[str] | None = None,
          languages: list[str] | None = None, html_only: bool = False,
          datestamp: str | None = None, log=print) -> list[BuildResult]:
    css = load_theme(cfg.theme, base_dir=cfg.base_dir)
    if datestamp is None and cfg.date_prefix:
        datestamp = date.today().isoformat()
    want_pdf = not html_only and "pdf" in cfg.formats
    want_docx = not html_only and "docx" in cfg.formats
    chrome = find_chrome(cfg.chrome) if want_pdf else None

    contents = {lang: load_content(cfg.content[lang])
                for lang in (languages or cfg.languages)}
    results: list[BuildResult] = []
    for variant in variants or cfg.variants:
        for lang, base_content in contents.items():
            content = dict(base_content,
                           facts=filter_facts(base_content["facts"], variant))
            docs = build_documents(cfg.person_name, content, cfg.level_max)
            html_dir = cfg.html_dir / variant / lang
            html_dir.mkdir(parents=True, exist_ok=True)
            for key in cfg.documents[lang]:
                local = content["doc_names"][key]
                # document title, also picked up as PDF metadata by Chrome
                title = f"{cfg.person_name} – {local}"
                html_path = html_dir / f"{local}.html"
                html_path.write_text(page(title, docs[key], css, lang),
                                     encoding="utf-8")
                expected = key_strings(cfg.person_name, content, key)

                docx_path = None
                docx_missing: list[str] = []
                if want_docx:
                    docx_dir = cfg.docx_dir / variant / lang
                    docx_dir.mkdir(parents=True, exist_ok=True)
                    docx_path = docx_dir / docx_filename(cfg.file_slug, local, lang,
                                                         datestamp)
                    build_docx(docx_path, cfg.person_name, content, cfg.level_max, key,
                               title=title, lang=lang, base_font=cfg.docx_font)
                    text = extract_docx_text(docx_path)
                    docx_missing = ([] if text is None
                                    else missing_strings(text, expected))
                    log(f"  wrote {variant}/{lang}/{docx_path.name}")
                    if docx_missing:
                        shown = "; ".join(docx_missing[:5])
                        more = (f" (+{len(docx_missing) - 5} more)"
                                if len(docx_missing) > 5 else "")
                        log(f"     !! DOCX check: {len(docx_missing)} key string(s) "
                            f"missing from the document text: {shown}{more}")

                if not want_pdf:
                    if html_only:
                        log(f"  wrote {variant}/{lang}/{local}.html")
                    results.append(BuildResult(variant, lang, key, html_path, None, True,
                                               docx_path=docx_path,
                                               docx_ats_missing=docx_missing))
                    continue
                pdf_dir = cfg.pdf_dir / variant / lang
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / pdf_filename(cfg.file_slug, local, lang, datestamp)
                log(f"  rendering {variant}/{local} [{lang}] ...")
                ok = render_pdf(chrome, html_path, pdf_path)
                ats_missing: list[str] = []
                if ok:
                    finalize_pdf(pdf_path, title=title, author=cfg.person_name)
                    text = extract_text(pdf_path)
                    if text is not None:
                        ats_missing = missing_strings(text, expected)
                log(f"     -> {pdf_path} {'OK' if ok else 'FAILED'}")
                if ats_missing:
                    shown = "; ".join(ats_missing[:5])
                    more = f" (+{len(ats_missing) - 5} more)" if len(ats_missing) > 5 else ""
                    log(f"     !! ATS check: {len(ats_missing)} key string(s) missing "
                        f"from the PDF text layer: {shown}{more}")
                results.append(BuildResult(variant, lang, key, html_path, pdf_path,
                                           ok, ats_missing))
    return results
