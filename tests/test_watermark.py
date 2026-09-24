"""Tests for the watermark (R29): config, HTML fragment and variant rules."""

from pathlib import Path

import pytest

from ergograph.builder import build
from ergograph.config import ConfigError, WatermarkSpec, load_config
from ergograph.render import page
from ergograph.watermark import watermark_html, watermark_uri

ARCHITECT = Path(__file__).parent.parent / "examples" / "software-architect"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


def _config(tmp_path, watermark: str, variants: str = "") -> Path:
    (tmp_path / "logo.svg").write_bytes(SVG)
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de, en]\n"
                 "content: {de: c.yaml, en: c.yaml}\n"
                 f"watermark: {watermark}\n{variants}", encoding="utf-8")
    return p


def test_watermark_path_form_uses_defaults(tmp_path):
    spec = load_config(_config(tmp_path, "logo.svg")).watermark
    assert spec.file.name == "logo.svg"
    assert (spec.opacity, spec.width) == (0.05, 0.6)
    assert spec.applies("onepager", "en") and spec.applies("cv", "de")


def test_watermark_documents_and_languages(tmp_path):
    spec = load_config(_config(
        tmp_path, "{file: logo.svg, opacity: 0.1, width: 0.5, "
                  "documents: [full], languages: [de]}")).watermark
    assert spec.applies("full", "de")
    assert not spec.applies("full", "en")
    assert not spec.applies("cv", "de")


@pytest.mark.parametrize("raw, message", [
    ("{file: logo.svg, opacity: 0}", "opacity"),
    ("{file: logo.svg, width: 1.5}", "width"),
    ("{file: logo.svg, colour: red}", "unknown option"),
    ("{file: logo.gif}", "unsupported image type"),
    ("{file: nope.svg}", "not found"),
    ("{file: logo.svg, documents: [letter]}", "unknown document"),
    ("{file: logo.svg, languages: [fr]}", "unknown language"),
])
def test_watermark_invalid_config_rejected(tmp_path, raw, message):
    with pytest.raises(ConfigError, match=message):
        load_config(_config(tmp_path, raw))


def test_watermark_off_for_anonymous_and_per_variant(tmp_path):
    cfg = load_config(_config(
        tmp_path, "logo.svg",
        "variants: {plain: {}, anon: {anonymous: true}, bare: {watermark: false}}\n"))
    assert cfg.spec("plain").watermark
    assert not cfg.spec("anon").watermark
    assert not cfg.spec("bare").watermark


def test_watermark_html_is_fixed_faint_and_textless(tmp_path):
    spec = load_config(_config(tmp_path, "{file: logo.svg, opacity: 0.05}")).watermark
    uri = watermark_uri(spec.file)
    assert uri.startswith("data:image/svg+xml;base64,")
    html = watermark_html(spec, uri)
    assert "position:fixed" in html and "opacity:0.05" in html
    assert "width:60%" in html and 'alt=""' in html and "pointer-events:none" in html
    doc = page("T", "<p>Body</p>", "", "de", watermark=html)
    assert doc.index('class="watermark"') < doc.index("<p>Body</p>")


def test_build_puts_the_watermark_into_named_variants_only(tmp_path):
    (tmp_path / "logo.svg").write_bytes(SVG)
    cfg = load_config(ARCHITECT / "config.yaml")
    cfg = type(cfg)(**{**cfg.__dict__, "html_dir": tmp_path / "html",
                       "flat_dir": None, "formats": ["md"],
                       "md_dir": tmp_path / "md",
                       "watermark": WatermarkSpec(tmp_path / "logo.svg", 0.05, 0.6,
                                                  ["full", "onepager"], None)})
    build(cfg, html_only=True, datestamp="2026-09-24", log=lambda *_: None)
    named = (tmp_path / "html" / "mit-stundensatz" / "de").glob("*.html")
    marked = {p.name for p in named if 'class="watermark"' in p.read_text("utf-8")}
    assert marked and all("lebenslauf" not in name.lower() for name in marked)
    anon = (tmp_path / "html" / "anonym").rglob("*.html")
    assert not any('class="watermark"' in p.read_text("utf-8") for p in anon)
