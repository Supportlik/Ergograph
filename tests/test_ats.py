import pytest

from ergograph.ats import key_strings, missing_strings, normalize, plain_text
from ergograph.config import filter_facts
from ergograph.render import build_documents


def test_normalize_collapses_whitespace_and_ligatures():
    assert normalize("a   b\n c") == "a b c"
    assert normalize("ﬂow chart") == "flow chart"      # fl ligature
    assert normalize("proﬁle") == "profile"            # fi ligature


def test_normalize_folds_case_and_hyphen_wraps():
    # CSS text-transform: uppercase reaches the PDF text layer as uppercase
    assert normalize("ECKDATEN") == normalize("Eckdaten")
    # a line wrap after a hyphen extracts as "Cloud- Infrastruktur"
    assert normalize("Cloud-\nInfrastruktur") == normalize("Cloud-Infrastruktur")
    # a line wrap inside a date range extracts as "11/2019– 03/2020"
    assert normalize("11/2019–\n03/2020") == normalize("11/2019–03/2020")


def test_plain_text_turns_br_into_space():
    # <br> renders as a line break in the PDF text layer
    assert plain_text("Development €120/h<br>Lead €140/h") == \
        normalize("Development €120/h Lead €140/h")


def test_plain_text_strips_tags_and_entities():
    assert plain_text('REST API, <a href="https://example.org">case study</a>.') == \
        normalize("REST API, case study.")
    assert plain_text("R&amp;D") == normalize("R&D")


def test_missing_strings_reports_absent_only():
    text = "Alexandra Argyriou\nSenior  Backend\nEngineer"
    assert missing_strings(text, ["Alexandra Argyriou", "Senior Backend Engineer"]) == []
    assert missing_strings(text, ["Cloud Architect"]) == ["Cloud Architect"]


def test_missing_strings_ignores_page_number_stamp():
    # a paragraph flowing across a page break has the page stamp in between
    text = "started on page one\n2 / 4\nand ends on page two"
    assert missing_strings(text, ["started on page one and ends on page two"]) == []


def test_key_strings_depend_on_document(example_content_de):
    content = dict(example_content_de,
                   facts=filter_facts(example_content_de["facts"], "mit-stundensatz"))
    cv = key_strings("Alexandra Argyriou", content, "cv")
    projects = key_strings("Alexandra Argyriou", content, "projects")
    full = key_strings("Alexandra Argyriou", content, "full")
    assert normalize("Senior Backend Engineer") in cv
    assert normalize("Orakel-Plattform") not in cv
    assert normalize("Orakel-Plattform") in projects
    assert normalize("2019 – heute") in projects   # project period is covered
    assert normalize("CKAD, Produktionsbetrieb") not in projects  # skill note
    assert set(cv) <= set(full) and set(projects) <= set(full)
    # full covers every piece of content, including long texts
    assert normalize("Eventgetriebene Plattform zur Sendungsverfolgung mit 40+ Services.") in full
    assert normalize("3/2019 – heute") in full                    # experience period
    assert normalize("Go · Kafka · Kubernetes · PostgreSQL") in full  # tech line


@pytest.mark.parametrize("document", ["cv", "projects", "skills", "full"])
def test_rendered_html_contains_all_key_strings(example_content_de, document):
    # Deterministic stand-in for the PDF check: the text layer of the PDF is
    # rendered from this HTML, so every key string must already be present in
    # the HTML's plain text.
    content = dict(example_content_de,
                   facts=filter_facts(example_content_de["facts"], "mit-stundensatz"))
    html = build_documents("Alexandra Argyriou", content, 6.0)[document]
    expected = key_strings("Alexandra Argyriou", content, document)
    assert missing_strings(plain_text(html), expected) == []
