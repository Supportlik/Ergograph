"""Command line: `ergograph build` and `ergograph validate`."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .builder import build
from .config import ConfigError, load_config, load_content


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ergograph",
        description="YAML-driven CV and dossier generator (HTML -> PDF via Chrome).")
    parser.add_argument("--version", action="version", version=f"ergograph {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="generate HTML and PDFs")
    b.add_argument("-c", "--config", default="config.yaml", help="path to the config.yaml")
    b.add_argument("--variant", action="append",
                   help="build only this variant (repeatable)")
    b.add_argument("--lang", action="append",
                   help="build only this language (repeatable)")
    b.add_argument("--html-only", action="store_true",
                   help="generate HTML only, no Chrome/PDF")
    b.add_argument("--date", default=None,
                   help="override the date prefix of the PDF file names (YYYY-MM-DD)")

    v = sub.add_parser("validate", help="check config and content files")
    v.add_argument("-c", "--config", default="config.yaml", help="path to the config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.command == "validate":
            for lang in cfg.languages:
                load_content(cfg.content[lang])
            print("OK: configuration and content files are valid.")
            return 0

        for variant in args.variant or []:
            if variant not in cfg.variants:
                raise ConfigError(f"Unknown variant '{variant}' "
                                  f"(configured: {', '.join(cfg.variants)})")
        for lang in args.lang or []:
            if lang not in cfg.languages:
                raise ConfigError(f"Unknown language '{lang}' "
                                  f"(configured: {', '.join(cfg.languages)})")
        results = build(cfg, variants=args.variant, languages=args.lang,
                        html_only=args.html_only, datestamp=args.date)
        failed = [r for r in results if not r.ok]
        if failed:
            print(f"Error: {len(failed)} document(s) could not be rendered.",
                  file=sys.stderr)
            return 1
        print("done.")
        return 0
    except (ConfigError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
