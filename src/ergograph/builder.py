"""Orchestration: load config + content, write HTML, render PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import Config, filter_facts, load_content
from .pdf import add_page_numbers, find_chrome, render_pdf
from .render import build_documents, load_theme, page


@dataclass
class BuildResult:
    variant: str
    lang: str
    document: str
    html_path: Path
    pdf_path: Path | None
    ok: bool


def pdf_filename(slug: str, doc_name: str, lang: str, datestamp: str | None) -> str:
    prefix = f"{datestamp}_" if datestamp else ""
    return f"{prefix}{slug}_{doc_name}_{lang}.pdf"


def build(cfg: Config, *, variants: list[str] | None = None,
          languages: list[str] | None = None, html_only: bool = False,
          datestamp: str | None = None, log=print) -> list[BuildResult]:
    css = load_theme(cfg.theme, base_dir=cfg.base_dir)
    if datestamp is None and cfg.date_prefix:
        datestamp = date.today().isoformat()
    chrome = None if html_only else find_chrome(cfg.chrome)

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
                html_path = html_dir / f"{local}.html"
                html_path.write_text(page(local, docs[key], css, lang),
                                     encoding="utf-8")
                if html_only:
                    log(f"  wrote {variant}/{lang}/{local}.html")
                    results.append(BuildResult(variant, lang, key, html_path, None, True))
                    continue
                pdf_dir = cfg.pdf_dir / variant / lang
                pdf_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = pdf_dir / pdf_filename(cfg.file_slug, local, lang, datestamp)
                log(f"  rendering {variant}/{local} [{lang}] ...")
                ok = render_pdf(chrome, html_path, pdf_path)
                if ok:
                    add_page_numbers(pdf_path)
                log(f"     -> {pdf_path} {'OK' if ok else 'FAILED'}")
                results.append(BuildResult(variant, lang, key, html_path, pdf_path, ok))
    return results
