"""Tests for 1.2.0: generalized variants, anonymous variants, photos,
the one-pager, the Markdown export and the flat output folder."""

import struct
import zipfile
from pathlib import Path

import pytest

from ergograph.ats import key_strings, leaked_identity, missing_strings_md, plain_text
from ergograph.builder import _publish_flat, build, flat_filename
from ergograph.config import ConfigError, check_documents, load_config, load_content
from ergograph.docx import build_docx
from ergograph.markdown import build_markdown
from ergograph.photo import load_photo
from ergograph.render import build_documents
from ergograph.variants import anonymize, identity_markers, resolve

ARCHITECT = Path(__file__).parent.parent / "examples" / "software-architect"


@pytest.fixture(scope="module")
def architect_config():
    return load_config(ARCHITECT / "config.yaml")


@pytest.fixture(scope="module")
def architect_de(architect_config):
    return load_content(architect_config.content["de"])


def _png(width, height) -> bytes:
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00")


# -- variants ---------------------------------------------------------------

def test_variants_mapping_form(architect_config):
    cfg = architect_config
    assert cfg.variants == ["mit-stundensatz", "ohne-stundensatz", "anonym"]
    anon = cfg.spec("anonym")
    assert anon.anonymous and not anon.photo
    assert "anonymous" in anon.tags and "anonym" in anon.tags
    assert cfg.documents_for("anonym", "de") == ["full", "onepager"]


def test_variants_list_form_still_works(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de]\ncontent: {de: c.yaml}\n"
                 "variants: [a, b]\n", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.variants == ["a", "b"]
    assert cfg.spec("a").tags == frozenset({"a"})


def test_unknown_variant_option_rejected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de]\ncontent: {de: c.yaml}\n"
                 "variants: {a: {colour: red}}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="colour"):
        load_config(p)


def test_resolve_filters_every_list():
    tree = {"items": [{"n": 1, "variants": ["x"]}, {"n": 2, "except_variants": ["x"]},
                      {"n": 3}]}
    assert resolve(tree, frozenset({"x"})) == {"items": [{"n": 1}, {"n": 3}]}
    assert resolve(tree, frozenset({"y"})) == {"items": [{"n": 2}, {"n": 3}]}


def test_by_variant_picks_first_active_tag_then_default():
    value = {"by_variant": {"a": "A", "b": "B", "default": "D"}}
    assert resolve(value, frozenset({"b", "a"})) == "A"
    assert resolve(value, frozenset({"b"})) == "B"
    assert resolve(value, frozenset({"z"})) == "D"


def test_by_variant_without_default_is_an_error():
    with pytest.raises(ConfigError, match="default"):
        resolve({"k": {"by_variant": {"a": 1}}}, frozenset({"z"}))


# -- anonymous variants -------------------------------------------------------

def test_anonymize_drops_contact_links_and_name(architect_de):
    content = resolve(architect_de, frozenset({"anonym", "anonymous"}))
    markers = identity_markers("Daniel Falkner", content)
    name, anon = anonymize(content, "de.yaml")
    assert name == "Kandidatenprofil"
    assert anon["contact"] == []
    assert all("url" not in c for c in anon["certs"])
    html = build_documents(name, anon, 6.0, documents=["full"])["full"]
    assert "<a " not in html
    assert "Landesbehörde (Verkehr)" in html
    assert leaked_identity(html, markers) == []


def test_anonymous_without_name_is_an_error():
    with pytest.raises(ConfigError, match="anonymous_name"):
        anonymize({"contact": []}, "x.yaml")


def test_identity_leak_is_found():
    markers = identity_markers("Daniel Falkner", {"contact": [{"value": "d@x.org"}]})
    assert leaked_identity("Kontakt: D@X.org", markers) == ["d@x.org"]
    assert leaked_identity("Herr Falkner", markers) == ["Falkner"]


# -- photos -------------------------------------------------------------------

def test_jpeg_size_is_read_from_the_header():
    photo = load_photo(ARCHITECT / "photo.jpg")
    assert (photo.width, photo.height) == (1000, 1250)
    assert photo.mime == "image/jpeg" and photo.ratio == 1.25


def test_png_size_is_read_from_the_header(tmp_path):
    path = tmp_path / "p.png"
    path.write_bytes(_png(40, 50))
    photo = load_photo(path)
    assert (photo.width, photo.height, photo.extension) == (40, 50, "png")


def test_photo_is_embedded_unchanged(architect_config, architect_de):
    photo = load_photo(architect_config.photo.file)
    content = resolve(architect_de, frozenset({"ohne-stundensatz"}))
    html = build_documents("Daniel Falkner", content, 6.0, {"full": photo},
                           ["full"])["full"]
    assert photo.data_uri() in html and 'class="header has-photo"' in html


def test_photo_spec_documents_languages_and_overrides(tmp_path):
    for name in ("a.jpg", "b.jpg"):
        (tmp_path / name).write_bytes(b"x")
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de, en]\n"
                 "content: {de: c.yaml, en: c.yaml}\n"
                 "photo: {file: a.jpg, languages: [de], files: {onepager: b.jpg}}\n",
                 encoding="utf-8")
    spec = load_config(p).photo
    assert spec.for_document("cv", "de").name == "a.jpg"
    assert spec.for_document("onepager", "de").name == "b.jpg"
    assert spec.for_document("cv", "en") is None
    assert spec.for_document("projects", "de") is None


def test_photo_missing_file_rejected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de]\ncontent: {de: c.yaml}\n"
                 "photo: nope.jpg\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not found"):
        load_config(p)


def test_docx_carries_the_photo(tmp_path, architect_config, architect_de):
    photo = load_photo(architect_config.photo.file)
    content = resolve(architect_de, frozenset({"ohne-stundensatz"}))
    out = tmp_path / "cv.docx"
    build_docx(out, "Daniel Falkner", content, 6.0, "cv", title="t", photo=photo)
    with zipfile.ZipFile(out) as zf:
        media = [n for n in zf.namelist() if n.endswith(".jpeg")]
        assert len(media) == 1 and zf.read(media[0]) == photo.data
        assert "image/jpeg" in zf.read("[Content_Types].xml").decode()


# -- one-pager ----------------------------------------------------------------

def test_onepager_resolves_project_references(architect_de):
    content = resolve(architect_de, frozenset({"ohne-stundensatz"}))
    html = build_documents("Daniel Falkner", content, 6.0,
                           documents=["onepager"])["onepager"]
    assert 'class="onepager"' in html and "AtlasCore" in html
    assert "09/2022–heute" in html        # period taken from the project item
    text = plain_text(html)
    for key in key_strings("Daniel Falkner", content, "onepager"):
        assert key in text, key


def test_onepager_unknown_ref_rejected(architect_de):
    content = resolve(architect_de, frozenset({"ohne-stundensatz"}))
    broken = dict(content, onepager=dict(content["onepager"],
                                         projects=[{"ref": "nope"}]))
    with pytest.raises(ConfigError, match="nope"):
        check_documents(broken, ["onepager"], "de.yaml")


def test_onepager_needs_its_block_only_when_built(architect_de):
    content = {k: v for k, v in architect_de.items() if k != "onepager"}
    check_documents(content, ["cv", "full"], "de.yaml")
    with pytest.raises(ConfigError, match="onepager"):
        check_documents(content, ["onepager"], "de.yaml")


# -- markdown -----------------------------------------------------------------

@pytest.mark.parametrize("document", ["cv", "projects", "skills", "full", "onepager"])
def test_markdown_contains_every_key_string(architect_de, document):
    content = resolve(architect_de, frozenset({"mit-stundensatz"}))
    text = build_markdown("Daniel Falkner", content, document)
    assert text.startswith("# Daniel Falkner\n")
    assert missing_strings_md(text, key_strings("Daniel Falkner", content, document)) == []


# -- flat folder --------------------------------------------------------------

def test_flat_filename_carries_variant_and_language():
    assert (flat_filename("A-B", "lebenslauf", "ohne", "de", "2026-09-24", "pdf", False)
            == "2026-09-24_A-B_lebenslauf_ohne_de.pdf")
    assert flat_filename("A-B", "cv", "default", "en", None, "md", True) == "A-B_cv_en.md"


def test_flat_publish_replaces_older_builds(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"new")
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "2026-01-01_A_cv_x_de.pdf").write_bytes(b"old")
    (flat / "2026-01-01_A_cv_y_de.pdf").write_bytes(b"other variant")
    _publish_flat(flat, src, "2026-09-24_A_cv_x_de.pdf", "2026-09-24")
    assert sorted(p.name for p in flat.iterdir()) == [
        "2026-01-01_A_cv_y_de.pdf", "2026-09-24_A_cv_x_de.pdf"]


def test_build_writes_markdown_and_flat_folder(tmp_path, architect_config):
    cfg = architect_config
    cfg = type(cfg)(**{**cfg.__dict__, "html_dir": tmp_path / "html",
                       "md_dir": tmp_path / "md", "flat_dir": tmp_path / "active",
                       "formats": ["md"]})
    results = build(cfg, datestamp="2026-09-24", log=lambda *_: None)
    assert all(not r.md_missing and not r.identity_leaks for r in results)
    names = sorted(p.name for p in (tmp_path / "active").iterdir())
    assert "2026-09-24_candidate-profile_one-pager_anonym_en.md" in names
    assert "2026-09-24_Daniel-Falkner_dossier-komplett_mit-stundensatz_de.md" in names
