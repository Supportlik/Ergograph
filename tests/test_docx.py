"""DOCX export: package validity, content identity and the HTML fragment rules.

The suite runs without Word and without network access (D8): a .docx is a ZIP
of XML parts, so validity is checked structurally (required parts present,
every part well-formed, relationship targets resolvable) and content identity
is checked with the same `ats.key_strings` machinery the PDF route uses (D13).
"""

import shutil
import zipfile
from xml.etree import ElementTree as ET

import pytest

from ergograph.ats import key_strings, missing_strings
from ergograph.builder import build, docx_filename
from ergograph.config import ConfigError, filter_facts, load_config
from ergograph.docx import build_docx, extract_text, fragment_runs

REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "word/footer1.xml",
    "word/_rels/document.xml.rels",
    "docProps/core.xml",
    "docProps/app.xml",
}

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@pytest.fixture
def written(tmp_path, example_config, example_content_de):
    """All four documents, written once per test module run."""
    content = dict(example_content_de,
                   facts=filter_facts(example_content_de["facts"], "ohne-stundensatz"))
    paths = {}
    for doc in ("cv", "projects", "skills", "full"):
        path = tmp_path / f"{doc}.docx"
        build_docx(path, example_config.person_name, content,
                   example_config.level_max, doc,
                   title=f"{example_config.person_name} - {doc}")
        paths[doc] = path
    return content, paths


def test_package_contains_the_required_parts(written):
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            assert zf.testzip() is None, f"{doc}: corrupt ZIP entry"
            assert REQUIRED_PARTS <= set(zf.namelist()), f"{doc}: missing parts"


def test_every_xml_part_is_well_formed(written):
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith(".png"):
                    continue          # level bars, checked separately
                ET.fromstring(zf.read(name))  # raises ParseError if malformed


def test_content_types_declares_every_part(written):
    """A part without a content type makes Word reject the file."""
    _, paths = written
    with zipfile.ZipFile(paths["full"]) as zf:
        types = ET.fromstring(zf.read("[Content_Types].xml"))
        defaults = {e.get("Extension") for e in types}
        overrides = {e.get("PartName") for e in types}
        for name in zf.namelist():
            if name == "[Content_Types].xml":
                continue
            ext = name.rsplit(".", 1)[-1]
            assert ext in defaults or f"/{name}" in overrides, name


def test_hyperlink_relationships_resolve(written):
    """Every r:id used in the document must exist in the rels part, otherwise
    Word reports the file as unreadable."""
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
        declared = {e.get("Id") for e in rels}
        used = set(ET.fromstring(doc_xml).iter())
        referenced = {el.get(f"{{{_R_NS}}}id") for el in used}
        referenced.discard(None)
        assert referenced <= declared, f"{doc}: dangling relationship id"
        # external links must be marked as such
        for e in rels:
            if e.get("Type", "").endswith("/hyperlink"):
                assert e.get("TargetMode") == "External"


def test_all_content_strings_are_in_the_text_layer(written, example_config):
    """Content identity with the HTML/PDF route: every YAML string must be
    extractable from the DOCX, the same guarantee R15 makes for PDFs."""
    content, paths = written
    for doc, path in paths.items():
        text = extract_text(path)
        assert text is not None
        expected = key_strings(example_config.person_name, content, doc)
        assert missing_strings(text, expected) == [], f"{doc}: content missing"


def test_variant_filter_reaches_the_docx(tmp_path, example_config, example_content_de):
    """The hourly rate must be absent from the variant that excludes it."""
    for variant, expected in (("mit-stundensatz", True), ("ohne-stundensatz", False)):
        content = dict(example_content_de,
                       facts=filter_facts(example_content_de["facts"], variant))
        path = tmp_path / f"cv-{variant}.docx"
        build_docx(path, example_config.person_name, content,
                   example_config.level_max, "cv", title="t")
        text = extract_text(path)
        assert ("100 €/h" in text) is expected


def test_full_document_contains_all_three_parts(written, example_config):
    content, paths = written
    full = extract_text(paths["full"])
    for doc in ("cv", "projects", "skills"):
        expected = key_strings(example_config.person_name, content, doc)
        assert missing_strings(full, expected) == []


def test_fragment_runs_handles_the_trusted_html_subset():
    runs = fragment_runs('plain <b>bold</b> <a href="https://x.test">link</a><br>after')
    assert ("plain ", False, False, None) in runs
    assert ("bold", True, False, None) in runs
    assert ("link", False, False, "https://x.test") in runs
    assert (None, False, False, None) in runs  # the <br>
    assert ("after", False, False, None) in runs


def test_xml_special_characters_survive_round_trip(tmp_path, example_config,
                                                   example_content_de):
    """Characters that are special in XML must not break the package.

    Note the D2 consequence: a value is a *trusted HTML fragment*, so an
    angle-bracket construct like `<Architecture>` counts as markup and is
    dropped here exactly as the browser drops it in the HTML route. Only
    text outside tags is guaranteed, and that is what this asserts.
    """
    content = dict(example_content_de, title="R&D \"quoted\" 'x' 100 % < 200 %",
                   facts=filter_facts(example_content_de["facts"], "ohne-stundensatz"))
    path = tmp_path / "escaped.docx"
    build_docx(path, example_config.person_name, content,
               example_config.level_max, "cv", title="t")
    with zipfile.ZipFile(path) as zf:
        ET.fromstring(zf.read("word/document.xml"))
    text = extract_text(path)
    assert "R&D" in text and '"quoted"' in text and "'x'" in text


def test_field_instructions_are_not_part_of_the_text_layer(written):
    """The footer carries PAGE/NUMPAGES fields; their instruction text must
    never leak into the extracted document text and confuse the ATS check."""
    _, paths = written
    text = extract_text(paths["cv"])
    assert "PAGE" not in text and "NUMPAGES" not in text


def test_extract_text_returns_none_for_a_non_docx(tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip file")
    assert extract_text(broken) is None


def test_docx_filename_with_and_without_date():
    assert docx_filename("Alexandra-Argyriou", "lebenslauf", "de", "2026-08-17") == \
        "2026-08-17_Alexandra-Argyriou_lebenslauf_de.docx"
    assert docx_filename("Alexandra-Argyriou", "cv", "en", None) == \
        "Alexandra-Argyriou_cv_en.docx"


def test_build_writes_docx_without_chrome(tmp_path, example_config):
    """`formats: [docx]` must build end to end without Chrome being involved."""
    shutil.copy(example_config.base_dir / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(example_config.base_dir / "content", tmp_path / "content")
    cfg = load_config(tmp_path / "config.yaml")
    cfg.formats = ["docx"]

    results = build(cfg, variants=["ohne-stundensatz"], languages=["de"],
                    datestamp="2026-08-17", log=lambda *_: None)

    assert results and all(r.ok and r.pdf_path is None for r in results)
    assert all(r.docx_path is not None and r.docx_path.exists() for r in results)
    assert all(r.docx_ats_missing == [] for r in results)
    assert not (tmp_path / "pdf").exists()
    assert (tmp_path / "docx/ohne-stundensatz/de"
            / "2026-08-17_Alexandra-Argyriou_lebenslauf_de.docx").exists()


def test_html_only_skips_docx(tmp_path, example_config):
    shutil.copy(example_config.base_dir / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(example_config.base_dir / "content", tmp_path / "content")
    cfg = load_config(tmp_path / "config.yaml")
    cfg.formats = ["pdf", "docx"]

    results = build(cfg, html_only=True, log=lambda *_: None)

    assert all(r.docx_path is None for r in results)
    assert not (tmp_path / "docx").exists()


def test_unknown_format_is_rejected(tmp_path, example_config):
    shutil.copytree(example_config.base_dir / "content", tmp_path / "content")
    (tmp_path / "config.yaml").write_text(
        (example_config.base_dir / "config.yaml").read_text(encoding="utf-8")
        + "\nformats: [pdf, rtf]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown format 'rtf'"):
        load_config(tmp_path / "config.yaml")


def test_formats_defaults_to_pdf_only(example_config):
    """Existing configs without `formats:` keep their previous behaviour."""
    assert example_config.formats == ["pdf"]


def test_skill_tags_are_shaded_pills_on_their_own_line(written):
    """A pill cannot be a rounded shape: a shape brings its own text box and
    the sidebar is already one, which makes Word refuse the file. So the pill
    is a shaded run, and since run shading always fills the *line*, each row
    of pills is its own paragraph whose line height is the pill height and
    whose spacing is the 4px gap between rows."""
    from ergograph.docx import _PILL_GAP, _PILL_LINE, TAG_BG
    content, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "roundRect" not in xml, "a shape inside the sidebar frame breaks Word"
    assert xml.count(f'w:fill="{TAG_BG}"') >= len(content["top_skills"])
    assert f'<w:spacing w:before="0" w:after="{_PILL_GAP}" ' \
           f'w:line="{_PILL_LINE}" w:lineRule="exact"/>' in xml
    for skill in content["top_skills"]:
        assert str(skill).replace(" ", "\u00a0") in xml, skill


def test_body_never_ends_with_a_table(written):
    """A table directly followed by w:sectPr is malformed; a trailing empty
    paragraph has to close the body."""
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "</w:tbl><w:sectPr" not in xml, f"{doc}: table runs into sectPr"


def test_table_rows_may_break_across_pages(written):
    """w:cantSplit is written as a bare element, never with a value.

    A reader that only tests for the element's presence would read
    val="false" as "keep together". It is used deliberately on the grid rows,
    which each hold one short block, so a position never breaks between its
    heading and its bullets."""
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        # every row that carries it must be a short one-block row of the grid
        assert xml.count("<w:cantSplit/>") == xml.count("<w:trPr>"), doc
        assert 'w:cantSplit w:val=' not in xml, f"{doc}: use presence, not a value"


def test_table_width_is_absolute_and_matches_its_columns(written):
    """Declaring the width in percent while asking for a fixed layout is
    contradictory; Word wants dxa plus the column widths that add up to it."""
    import re as _re
    _, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    for tbl in _re.findall(r"<w:tbl>.*?</w:tblGrid>", xml, _re.DOTALL):
        width = int(_re.search(r'<w:tblW w:w="(\d+)" w:type="dxa"/>', tbl).group(1))
        cols = [int(w) for w in _re.findall(r'<w:gridCol w:w="(\d+)"/>', tbl)]
        assert sum(cols) == width, (width, cols)


def test_cv_puts_the_sidebar_in_an_anchored_frame(written):
    """The CV keeps the side-by-side layout of the PDF, but without a table:
    the reading view of Word for the web moves any table to a fresh page as
    soon as something precedes it, whatever its height, while the editing
    view renders the same file correctly. The main column is therefore
    indented flowing text and the sidebar an anchored frame beside it."""
    from ergograph.docx import _EMU_TWIP, _GAP, _SIDE_W
    _, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "<w:tbl>" not in xml, "the CV must not use a table"
    assert "<wp:anchor" in xml and "<wps:txbx>" in xml
    assert f'cx="{_SIDE_W * _EMU_TWIP}"' in xml
    # every paragraph of the main column clears the sidebar
    body = xml[xml.index("</w:txbxContent>"):]
    assert f'<w:ind w:left="{_SIDE_W + _GAP}"' in body


def test_indent_sits_in_the_schema_required_position(written):
    """w:pPr children are order-sensitive: w:ind must follow keepNext/pBdr and
    precede w:tabs and w:spacing, otherwise Word rejects the part."""
    import re
    _, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    for ppr in re.findall(r"<w:pPr>.*?</w:pPr>", xml):
        if "<w:ind " not in ppr:
            continue
        pos = ppr.index("<w:ind ")
        for later in ("<w:tabs>", "<w:spacing "):
            if later in ppr:
                assert pos < ppr.index(later), ppr
        for earlier in ("<w:keepNext/>", "<w:pBdr>"):
            if earlier in ppr:
                assert ppr.index(earlier) < pos, ppr


def test_widow_control_is_on_everywhere(written):
    """Without it Word happily leaves a single trailing word on its own page
    (observed: the last publication summary spilling one word onto page 3)."""
    import re
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        pprs = re.findall(r"<w:pPr>.*?</w:pPr>", xml)
        assert pprs, doc
        assert all("<w:widowControl/>" in p for p in pprs), doc


def test_short_meta_paragraphs_keep_their_lines_together(written):
    """Publication summaries and the small org/institution lines must not be
    split across a page break."""
    _, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "<w:keepLines/>" in xml


def test_skills_matrix_flows_through_a_two_column_section(written):
    """`column-count: 2` on `.skills-cols` is a two-column Word section, and
    it has to start *continuous*, otherwise the matrix leaves its heading
    behind on the previous page. The heading and the legend are outside
    `.skills-cols`, so they end the one-column section before it."""
    from ergograph.docx import _COL_GAP
    content, paths = written
    for doc in ("full", "skills"):
        with zipfile.ZipFile(paths[doc]) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert f'<w:cols w:num="2" w:space="{_COL_GAP}"' in xml, doc
        assert xml.count("<w:sectPr>") == 2, doc
        assert '<w:type w:val="continuous"/>' in xml, doc
        # the heading and the legend are in the one-column part, i.e. the
        # break comes after them and the two-column properties after that
        skills = content["labels"]["skills"]
        legend = content["labels"]["legend"]
        boundary = xml.index('<w:type w:val="continuous"/>')
        for text in (skills, legend):
            assert xml.index(text.split("<")[0][:12]) < boundary, (doc, text)


def test_documents_without_the_matrix_stay_one_column(written):
    _, paths = written
    for doc in ("cv", "projects"):
        with zipfile.ZipFile(paths[doc]) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert '<w:cols w:num="2"' not in xml, doc
        assert xml.count("<w:sectPr>") == 1, doc


def test_level_bars_are_embedded_pictures(written):
    """`.skill .bar` is a rounded, gradient-filled stadium. Word has nothing
    like it in the text flow, so the bar is an inline PNG; every reference
    has to resolve to a media part and every part has to be a real PNG."""
    import re
    _, paths = written
    for doc in ("skills", "full"):
        with zipfile.ZipFile(paths[doc]) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
            rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            media = [n for n in zf.namelist() if n.startswith("word/media/")]
            assert media, doc
            for name in media:
                assert zf.read(name).startswith(b"\x89PNG\r\n\x1a\n"), name

        embeds = set(re.findall(r'<a:blip r:embed="([^"]+)"', xml))
        assert embeds, doc
        targets = dict(re.findall(r'Id="([^"]+)"[^>]*Target="media/([^"]+)"',
                                  rels))
        for rid in embeds:
            assert rid in targets, (doc, rid)
            assert f"word/media/{targets[rid]}" in media

        ids = re.findall(r'<wp:docPr id="(\d+)"', xml)
        assert len(ids) == len(set(ids)), "wp:docPr ids must be unique"


def test_a_category_is_never_split(written):
    """`.skill-cat { break-inside: avoid }`: every paragraph of a category
    but the last is bound to the next, so a column break cannot leave a note
    behind or tear a category in half. keepNext only binds *paragraphs*,
    which is why the matrix is not a table."""
    import re
    _, paths = written
    with zipfile.ZipFile(paths["skills"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    # everything after the inline sectPr is the two-column part
    tail = xml[xml.index("</w:sectPr>"):]
    paragraphs = re.findall(r"<w:p>.*?</w:p>", tail, re.S)
    assert paragraphs, "no matrix paragraphs found"
    assert "<w:tbl>" not in tail, "the matrix must not be a table"
    bound = sum("<w:keepNext/>" in par for par in paragraphs)
    assert bound >= len(paragraphs) - len(written[0]["skills"]) - 1


def test_long_skill_names_are_wrapped_to_the_name_column(written):
    """A tab stop cannot wrap, so a name wider than the 140px column is
    broken here; otherwise it pushes the bar and level out of the grid."""
    from ergograph.docx import _SKILL_NAME_W, _text_width, _wrap_name
    limit = _SKILL_NAME_W / 15
    for name in ("Java", "Microservices & Cloud-Architekturen",
                 "Testing (JUnit 5, Unit/Integration)"):
        lines = _wrap_name(name, limit, 7)
        assert " ".join(lines) == name, name
        for line in lines[:-1]:
            assert _text_width(line, 7) <= limit, (name, line)


def test_level_bar_spans_the_grid_column(written):
    """The bar is the `1fr` of `grid-template-columns: 140px 1fr auto`, so it
    has to be what is left of the column after name, gaps and level. The old
    stand-in (22 shaded spaces) came out at about a third of that."""
    from ergograph.docx import (_BAR_H, _COL_W, _EMU_PX, _SKILL_GAP,
                                _SKILL_LVL_W, _SKILL_NAME_W)
    _, paths = written
    expected = _COL_W - _SKILL_NAME_W - 2 * _SKILL_GAP - _SKILL_LVL_W
    cx = round(expected / 15 * _EMU_PX)
    cy = round(_BAR_H * _EMU_PX)
    with zipfile.ZipFile(paths["skills"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert f'<wp:extent cx="{cx}" cy="{cy}"/>' in xml


def test_body_never_ends_with_a_full_empty_paragraph(written):
    """A table has to be followed by a paragraph, but a visible one opens an
    extra page whenever the last page is full — the CV ended on one, the
    combined dossier on a seventh. The separator is hidden text."""
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        if not xml.rstrip().endswith("</w:tbl></w:body></w:document>"):
            tail = xml[xml.rindex("</w:tbl>"):] if "</w:tbl>" in xml else ""
            if tail.count("<w:p>") == 1:
                assert "<w:vanish/>" in tail, doc


def test_page_breaks_are_a_property_of_the_paragraph(written):
    """`page-break-before: always` as its own paragraph would leave a blank
    line at the top of the new page, which the CSS does not — and in the
    dossier that line comes off the page the matrix has to fit on."""
    _, paths = written
    with zipfile.ZipFile(paths["full"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert '<w:br w:type="page"/>' not in xml
    assert xml.count("<w:pageBreakBefore/>") == 2   # projects and skills


def test_inline_section_properties_follow_the_schema_order(written):
    """Inside w:pPr the order of children is fixed: w:sectPr comes after
    w:rPr. Word refuses to open a document that has them the other way."""
    import re
    _, paths = written
    for doc in ("full", "skills"):
        with zipfile.ZipFile(paths[doc]) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        for ppr in re.findall(r"<w:pPr>.*?</w:pPr>", xml, re.S):
            if "<w:sectPr>" not in ppr or "<w:rPr>" not in ppr:
                continue
            assert ppr.index("<w:rPr>") < ppr.index("<w:sectPr>"), doc


def test_every_paragraph_states_an_exact_line_height(written):
    """CSS multiplies `line-height: 1.5` by the font size, Word's multiple by
    the font's own line height — a quarter taller, a page over a CV. Every
    paragraph therefore carries an exact height."""
    _, paths = written
    for doc, path in paths.items():
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert 'w:lineRule="auto"' not in xml, doc


def test_periods_keep_their_own_room(written):
    """`.entry .period { white-space: nowrap }` in a flex row: the text beside
    a period wraps before it instead of the period being broken in half. The
    paragraph reserves that room with a right indent."""
    from ergograph.docx import _period_room
    content, paths = written
    period = content["experience"][0]["period"]
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    room = _period_room(period)
    assert room > 0
    role = xml[xml.index(period.split("–")[0][:7]) - 2000:]
    assert f'w:right="{room}"' in role[:2000]


def test_pill_labels_never_break(written):
    """A `.tag` is an inline-block: it moves to the next line as a whole. In
    Word the pill is a shaded run, so a plain space inside the label would
    split the pill and its shading across two lines."""
    import re
    _, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    for run in re.findall(r"<w:r>(?:(?!</w:r>).)*?<w:shd[^>]*TAG|", xml):
        pass
    for text in re.findall(r'<w:shd w:val="clear" w:color="auto" w:fill="EFF6FF"/>'
                           r'(?:(?!</w:r>).)*?<w:t[^>]*>(.*?)</w:t>', xml, re.S):
        assert " " not in text.strip(" "), text


def test_a_position_is_never_split(written):
    """`.entry { break-inside: avoid }`: a position moves to the next page as
    a whole, which is what keeps the break points the same as in the PDF."""
    import re
    content, paths = written
    with zipfile.ZipFile(paths["cv"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    body = xml[xml.index("</w:txbxContent>"):]
    role = content["experience"][0]["role"]
    start = body.index(role)
    block = body[start:start + 4000]
    paragraphs = re.findall(r"<w:p>.*?</w:p>", block, re.S)
    # every paragraph of the position but its last is bound to the next one
    entry = paragraphs[:1 + len(content["experience"][0]["bullets"])]
    for par in entry[:-1]:
        assert "<w:keepNext/>" in par
