import pytest

from ergograph.config import ConfigError, filter_facts, load_config, load_content


def test_example_config_loads(example_config):
    cfg = example_config
    assert cfg.person_name == "Alexandra Argyriou"
    assert cfg.file_slug == "Alexandra-Argyriou"
    assert cfg.languages == ["de", "en"]
    assert cfg.variants == ["mit-stundensatz", "ohne-stundensatz"]
    assert cfg.documents["de"] == ["cv", "projects", "skills", "full"]
    assert cfg.documents["en"] == ["full"]
    assert cfg.level_max == 6.0
    assert cfg.content["de"].is_file()


def test_paths_relative_to_config_file(example_config):
    assert example_config.html_dir == example_config.base_dir / ".build" / "html"
    assert example_config.pdf_dir.parent == example_config.base_dir


def test_missing_config_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nowhere/config.yaml")


def test_missing_person_name(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {}\nlanguages: [de]\ncontent: {de: c.yaml}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="name"):
        load_config(p)


def test_missing_content_for_language(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de, en]\ncontent: {de: c.yaml}\n",
                  encoding="utf-8")
    with pytest.raises(ConfigError, match="language 'en'"):
        load_config(p)


def test_unknown_document_rejected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de]\ncontent: {de: c.yaml}\n"
                 "documents: [cv, brief]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="brief"):
        load_config(p)


def test_documents_flat_list_applies_to_all_languages(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("person: {name: X}\nlanguages: [de, en]\n"
                 "content: {de: c.yaml, en: c.yaml}\ndocuments: [cv, full]\n",
                 encoding="utf-8")
    cfg = load_config(p)
    assert cfg.documents == {"de": ["cv", "full"], "en": ["cv", "full"]}


def test_content_missing_required_key(tmp_path):
    p = tmp_path / "de.yaml"
    p.write_text("title: X\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="tagline"):
        load_content(p)


def test_content_skill_without_level(tmp_path, example_config):
    import yaml
    data = yaml.safe_load(example_config.content["de"].read_text(encoding="utf-8"))
    del data["skills"][0]["items"][0]["level"]
    p = tmp_path / "de.yaml"
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="level"):
        load_content(p)


def test_filter_facts_keeps_order_and_filters_variants(example_content_de):
    facts = example_content_de["facts"]
    mit = filter_facts(facts, "mit-stundensatz")
    ohne = filter_facts(facts, "ohne-stundensatz")
    assert [f["label"] for f in mit] == ["Verfügbarkeit", "Stundensatz", "Auslastung"]
    assert [f["label"] for f in ohne] == ["Verfügbarkeit", "Auslastung"]
