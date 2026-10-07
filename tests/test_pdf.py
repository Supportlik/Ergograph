from pathlib import Path

from ergograph import pdf


def _args(monkeypatch, env=None, euid=1000):
    monkeypatch.delenv("ERGOGRAPH_CHROME_NO_SANDBOX", raising=False)
    if env is not None:
        monkeypatch.setenv("ERGOGRAPH_CHROME_NO_SANDBOX", env)
    monkeypatch.setattr(pdf.os, "geteuid", lambda: euid, raising=False)
    return pdf.chrome_args("chrome", Path("in.html"), Path("out.pdf"))


def test_sandbox_stays_on_by_default(monkeypatch):
    assert "--no-sandbox" not in _args(monkeypatch)


def test_sandbox_off_via_environment(monkeypatch):
    assert "--no-sandbox" in _args(monkeypatch, env="1")


def test_sandbox_off_as_root(monkeypatch):
    assert "--no-sandbox" in _args(monkeypatch, euid=0)


def test_print_target_and_source(monkeypatch):
    args = _args(monkeypatch)
    assert args[0] == "chrome"
    assert "--print-to-pdf=out.pdf" in args
    assert args[-1] == "in.html"
