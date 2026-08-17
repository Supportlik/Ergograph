import shutil

from ergograph.builder import build, pdf_filename
from ergograph.config import load_config


def test_pdf_filename_with_and_without_date():
    assert pdf_filename("Alexandra-Argyriou", "lebenslauf", "de", "2026-08-17") == \
        "2026-08-17_Alexandra-Argyriou_lebenslauf_de.pdf"
    assert pdf_filename("Alexandra-Argyriou", "cv", "en", None) == \
        "Alexandra-Argyriou_cv_en.pdf"


def test_build_html_only(tmp_path, example_config):
    # copy the example into a tmp directory so the repo stays clean
    shutil.copy(example_config.base_dir / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(example_config.base_dir / "content", tmp_path / "content")
    cfg = load_config(tmp_path / "config.yaml")

    results = build(cfg, html_only=True, log=lambda *_: None)

    # 2 Varianten x (4 Dokumente de + 1 Dokument en)
    assert len(results) == 10
    assert all(r.ok and r.pdf_path is None for r in results)
    cv = (tmp_path / "html/mit-stundensatz/de/lebenslauf.html").read_text(encoding="utf-8")
    assert "Alexandra Argyriou" in cv and "100 €/h" in cv
    cv_ohne = (tmp_path / "html/ohne-stundensatz/de/lebenslauf.html").read_text(encoding="utf-8")
    assert "Stundensatz" not in cv_ohne
    assert (tmp_path / "html/mit-stundensatz/en/dossier-complete.html").exists()
    assert not (tmp_path / "html/mit-stundensatz/en/cv.html").exists()
    assert not (tmp_path / "pdf").exists()


def test_build_respects_variant_and_lang_filter(tmp_path, example_config):
    shutil.copy(example_config.base_dir / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(example_config.base_dir / "content", tmp_path / "content")
    cfg = load_config(tmp_path / "config.yaml")

    results = build(cfg, variants=["ohne-stundensatz"], languages=["de"],
                    html_only=True, log=lambda *_: None)

    assert len(results) == 4
    assert {(r.variant, r.lang) for r in results} == {("ohne-stundensatz", "de")}
