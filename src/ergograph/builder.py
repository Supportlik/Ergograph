"""Orchestration: load config + content, write HTML, render PDFs."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .ats import (key_strings, leaked_identity, missing_strings,
                  missing_strings_md)
from .config import Config, check_documents, load_content
from .docx import build_docx
from .docx import extract_text as extract_docx_text
from .markdown import build_markdown
from .pdf import extract_text, finalize_pdf, find_chrome, page_count, render_pdf
from .photo import load_photo
from .render import build_documents, load_theme, page
from .variants import anonymize, identity_markers, resolve


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
    md_path: Path | None = None
    md_missing: list[str] = field(default_factory=list)
    #: Pages of a document that must fit on one (the one-pager); None if fine.
    overflow_pages: int | None = None
    #: Name parts or contact values found in an anonymous document.
    identity_leaks: list[str] = field(default_factory=list)


def output_filename(slug: str, doc_name: str, lang: str, datestamp: str | None,
                    suffix: str) -> str:
    prefix = f"{datestamp}_" if datestamp else ""
    return f"{prefix}{slug}_{doc_name}_{lang}.{suffix}"


def pdf_filename(slug: str, doc_name: str, lang: str, datestamp: str | None) -> str:
    return output_filename(slug, doc_name, lang, datestamp, "pdf")


def docx_filename(slug: str, doc_name: str, lang: str, datestamp: str | None) -> str:
    return output_filename(slug, doc_name, lang, datestamp, "docx")


def flat_filename(slug: str, doc_name: str, variant: str, lang: str,
                  datestamp: str | None, suffix: str, single_variant: bool,
                  label: str | None = None) -> str:
    """Name in the flat folder: the variant (or its `flat_label`) joins the
    name unless there is only one variant or the label is empty."""
    part = variant if label is None else label
    middle = doc_name if single_variant or not part else f"{doc_name}_{part}"
    return output_filename(slug, middle, lang, datestamp, suffix)


def _publish_flat(flat_dir: Path, source: Path, name: str, datestamp: str | None) -> None:
    """Copy `source` into the flat folder, replacing earlier builds of the
    same document (the same name with any date prefix)."""
    flat_dir.mkdir(parents=True, exist_ok=True)
    undated = name[len(datestamp) + 1:] if datestamp else name
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2}_)?" + re.escape(undated))
    for old in flat_dir.iterdir():
        if old.is_file() and pattern.fullmatch(old.name):
            old.unlink()
    shutil.copy2(source, flat_dir / name)


def _html_text(html_doc: str) -> str:
    body = re.sub(r"<(style|title)[^>]*>.*?</\1>", " ", html_doc, flags=re.S)
    body = re.sub(r"<img[^>]*>", " ", body)
    return re.sub(r"<[^>]+>", " ", body)


def build(cfg: Config, *, variants: list[str] | None = None,
          languages: list[str] | None = None, html_only: bool = False,
          datestamp: str | None = None, log=print) -> list[BuildResult]:
    css = load_theme(cfg.theme, base_dir=cfg.base_dir)
    if datestamp is None and cfg.date_prefix:
        datestamp = date.today().isoformat()
    want_pdf = not html_only and "pdf" in cfg.formats
    want_docx = not html_only and "docx" in cfg.formats
    want_md = not html_only and "md" in cfg.formats
    chrome = find_chrome(cfg.chrome) if want_pdf else None
    single_variant = len(cfg.variants) == 1

    contents = {lang: load_content(cfg.content[lang])
                for lang in (languages or cfg.languages)}
    photo_cache: dict[Path, object] = {}

    def photo(path):
        if path is None:
            return None
        if path not in photo_cache:
            photo_cache[path] = load_photo(path)
        return photo_cache[path]

    results: list[BuildResult] = []
    for variant in variants or cfg.variants:
        spec = cfg.spec(variant)
        for lang, base_content in contents.items():
            where = str(cfg.content[lang])
            content = resolve(base_content, spec.tags, where)
            name, slug, author = cfg.person_name, cfg.file_slug, cfg.person_name
            markers: list[str] = []
            if spec.anonymous:
                markers = identity_markers(cfg.person_name, content)
                name, content = anonymize(content, where)
                slug = str(content.get("anonymous_slug") or cfg.anonymous_slug)
                author = ""
            # the name part of the variant in flat file names, per language
            label = (content.get("variant_names") or {}).get(variant, spec.flat_label)
            doc_keys = cfg.documents_for(variant, lang)
            check_documents(content, doc_keys, where)
            photos = {}
            if spec.photo and cfg.photo is not None:
                photos = {doc: photo(cfg.photo.for_document(doc, lang))
                          for doc in doc_keys}
            docs = build_documents(name, content, cfg.level_max, photos, doc_keys)
            html_dir = cfg.html_dir / variant / lang
            html_dir.mkdir(parents=True, exist_ok=True)
            for key in doc_keys:
                local = content["doc_names"][key]
                one_page = key == "onepager"
                # document title, also picked up as PDF metadata by Chrome
                title = f"{name} – {local}"
                html_path = html_dir / f"{local}.html"
                html_doc = page(title, docs[key], css, lang,
                                "onepager-doc" if one_page else "")
                html_path.write_text(html_doc, encoding="utf-8")
                expected = key_strings(name, content, key)
                leaks = leaked_identity(_html_text(html_doc), markers)

                def flat(path: Path, suffix: str) -> None:
                    wanted = (spec.flat_documents if spec.flat_documents is not None
                              else cfg.flat_documents)
                    if wanted is not None and key not in wanted:
                        return
                    if cfg.flat_dir is not None:
                        target = (cfg.flat_dir / suffix if cfg.flat_by_format
                                  else cfg.flat_dir)
                        _publish_flat(target, path, flat_filename(
                            slug, local, variant, lang, datestamp, suffix,
                            single_variant, label), datestamp)

                md_path = None
                md_missing: list[str] = []
                if want_md:
                    md_dir = cfg.md_dir / variant / lang
                    md_dir.mkdir(parents=True, exist_ok=True)
                    md_path = md_dir / output_filename(slug, local, lang, datestamp, "md")
                    text = build_markdown(name, content, key)
                    md_path.write_text(text, encoding="utf-8")
                    md_missing = missing_strings_md(text, expected)
                    leaks += leaked_identity(text, markers)
                    log(f"  wrote {variant}/{lang}/{md_path.name}")
                    if md_missing:
                        log(f"     !! MD check: {len(md_missing)} key string(s) "
                            f"missing: {'; '.join(md_missing[:5])}")
                    flat(md_path, "md")

                docx_path = None
                docx_missing: list[str] = []
                # a landscape multi-column page is not reproduced in Word:
                # the one-pager exists as PDF (and Markdown) only
                if want_docx and not one_page:
                    docx_dir = cfg.docx_dir / variant / lang
                    docx_dir.mkdir(parents=True, exist_ok=True)
                    docx_path = docx_dir / docx_filename(slug, local, lang, datestamp)
                    build_docx(docx_path, name, content, cfg.level_max, key,
                               title=title, lang=lang, base_font=cfg.docx_font,
                               photo=photos.get(key), author=author)
                    text = extract_docx_text(docx_path)
                    docx_missing = ([] if text is None
                                    else missing_strings(text, expected))
                    if text is not None:
                        leaks += leaked_identity(text, markers)
                    log(f"  wrote {variant}/{lang}/{docx_path.name}")
                    if docx_missing:
                        shown = "; ".join(docx_missing[:5])
                        more = (f" (+{len(docx_missing) - 5} more)"
                                if len(docx_missing) > 5 else "")
                        log(f"     !! DOCX check: {len(docx_missing)} key string(s) "
                            f"missing from the document text: {shown}{more}")
                    flat(docx_path, "docx")

                if not want_pdf:
                    if html_only:
                        log(f"  wrote {variant}/{lang}/{local}.html")
                    results.append(BuildResult(
                        variant, lang, key, html_path, None, True,
                        docx_path=docx_path, docx_ats_missing=docx_missing,
                        md_path=md_path, md_missing=md_missing,
                        identity_leaks=sorted(set(leaks))))
                    continue
                pdf_dir = cfg.pdf_dir / variant / lang
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / pdf_filename(slug, local, lang, datestamp)
                log(f"  rendering {variant}/{local} [{lang}] ...")
                ok = render_pdf(chrome, html_path, pdf_path)
                ats_missing: list[str] = []
                overflow = None
                if ok:
                    finalize_pdf(pdf_path, title=title, author=author or None,
                                 page_numbers=not one_page)
                    text = extract_text(pdf_path)
                    if text is not None:
                        ats_missing = missing_strings(text, expected)
                        leaks += leaked_identity(text, markers)
                    pages = page_count(pdf_path)
                    if one_page and pages and pages > 1:
                        overflow = pages
                log(f"     -> {pdf_path} {'OK' if ok else 'FAILED'}")
                if ats_missing:
                    shown = "; ".join(ats_missing[:5])
                    more = f" (+{len(ats_missing) - 5} more)" if len(ats_missing) > 5 else ""
                    log(f"     !! ATS check: {len(ats_missing)} key string(s) missing "
                        f"from the PDF text layer: {shown}{more}")
                if overflow:
                    log(f"     !! one-pager runs over {overflow} pages; shorten the "
                        f"onepager block")
                if leaks:
                    log(f"     !! anonymous variant shows identity: "
                        f"{'; '.join(sorted(set(leaks)))}")
                if ok:
                    flat(pdf_path, "pdf")
                results.append(BuildResult(
                    variant, lang, key, html_path, pdf_path, ok, ats_missing,
                    docx_path=docx_path, docx_ats_missing=docx_missing,
                    md_path=md_path, md_missing=md_missing,
                    overflow_pages=overflow, identity_leaks=sorted(set(leaks))))
    return results
