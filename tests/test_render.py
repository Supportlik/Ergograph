import pytest

from ergograph.config import ConfigError, filter_facts
from ergograph.render import (PAGE_BREAK, SECTION_GAP, build_documents,
                              load_theme, page, projects_section,
                              skills_section)


@pytest.fixture()
def docs(example_content_de):
    content = dict(example_content_de,
                   facts=filter_facts(example_content_de["facts"], "mit-stundensatz"))
    return build_documents("Alexandra Argyriou", content, 6.0)


def test_all_documents_built(docs):
    assert set(docs) == {"cv", "projects", "skills", "full"}


def test_cv_contains_name_sections_and_facts(docs):
    cv = docs["cv"]
    assert '<div class="name">Alexandra Argyriou</div>' in cv
    for label in ("Berufserfahrung", "Ausbildung", "Publikationen", "Eckdaten"):
        assert label in cv
    assert "100 €/h" in cv  # hourly-rate fact in the mit-stundensatz variant
    # optional publication summary renders after the venue
    assert "Vergleicht Tracing-Strategien" in cv


def test_variant_without_rate(example_content_de):
    content = dict(example_content_de,
                   facts=filter_facts(example_content_de["facts"], "ohne-stundensatz"))
    cv = build_documents("X", content, 6.0)["cv"]
    assert "Stundensatz" not in cv


def test_full_document_composition(docs):
    full = docs["full"]
    assert full.count(PAGE_BREAK) == 2    # each part starts on a fresh page
    assert full.count(SECTION_GAP) == 0
    assert full.startswith(docs["cv"])  # full starts with the complete CV


def test_skill_bar_percentage(example_content_de):
    html = skills_section(example_content_de, 6.0)
    # Go: level 5 of 6 -> 83 %
    assert "width:83%" in html
    # half levels render without a trailing .0
    assert '<span class="lvl">4.5</span>' in html
    assert '<span class="lvl">5</span>' in html


def test_project_description_paragraphs(example_content_de):
    html = projects_section(example_content_de)
    # list description -> two pd divs
    assert html.count('<div class="pd">Event') == 1
    assert '<div class="pd">Verantwortlich für Architektur' in html
    # string description with inline HTML is preserved
    assert '<a href="https://github.com/Supportlik/Ergograph">Fallstudie</a>' in html


def test_project_period_and_org(example_content_de):
    html = projects_section(example_content_de)
    # period renders right-aligned next to the title, org as subtitle
    assert '<span class="ph">Orakel-Plattform</span><span class="pp">2019 – heute</span>' in html
    assert '<div class="po">Delphi Systems GmbH</div>' in html


def test_structured_bullet(docs):
    cv = docs["cv"]
    assert '<span class="li-period">2017–2018</span>' in cv
    assert '<div class="li-sub">Hellas Analytics</div>' in cv
    # plain string bullets still render as before
    assert "<li>Einführung von Tracing und SLO-basiertem Monitoring" in cv


def test_page_wraps_body(example_content_de):
    html = page("lebenslauf", "<p>x</p>", "body{}", "de")
    assert html.startswith("<!doctype html>")
    assert '<html lang="de">' in html
    assert "<title>lebenslauf</title>" in html
    assert "<p>x</p>" in html


def test_bundled_theme_loads():
    css = load_theme("modern")
    assert "@page" in css


def test_unknown_theme_raises():
    with pytest.raises(ConfigError, match="Unknown theme"):
        load_theme("barock")


def test_custom_theme_from_file(tmp_path):
    (tmp_path / "eigen.css").write_text("body { color: red; }", encoding="utf-8")
    assert "red" in load_theme("eigen.css", base_dir=tmp_path)
