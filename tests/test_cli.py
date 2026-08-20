import shutil
from pathlib import Path

from ergograph.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples" / "minimal"


def _copy_example(tmp_path):
    shutil.copy(EXAMPLES / "config.yaml", tmp_path / "config.yaml")
    shutil.copytree(EXAMPLES / "content", tmp_path / "content")
    return tmp_path / "config.yaml"


def test_validate_ok(tmp_path, capsys):
    cfg = _copy_example(tmp_path)
    assert main(["validate", "-c", str(cfg)]) == 0
    assert "OK" in capsys.readouterr().out


def test_build_html_only(tmp_path):
    cfg = _copy_example(tmp_path)
    assert main(["build", "-c", str(cfg), "--html-only"]) == 0
    assert (tmp_path / ".build/html/mit-stundensatz/de/dossier-komplett.html").exists()


def test_unknown_variant_fails(tmp_path, capsys):
    cfg = _copy_example(tmp_path)
    assert main(["build", "-c", str(cfg), "--variant", "does-not-exist"]) == 1
    assert "Unknown variant" in capsys.readouterr().err


def test_missing_config_fails(capsys):
    assert main(["validate", "-c", "/nowhere/config.yaml"]) == 1
    assert "Error" in capsys.readouterr().err
