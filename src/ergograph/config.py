"""Loading and validating the steering config and the content files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Error in the config.yaml or in a content file."""


#: Canonical document keys; localized file names come from `doc_names`
#: in the respective content file.
CANONICAL_DOCUMENTS = ("cv", "projects", "skills", "full")

REQUIRED_CONTENT_KEYS = (
    "title", "tagline", "labels", "doc_names", "contact", "facts",
    "languages", "certs", "top_skills", "education", "experience",
    "publications", "projects", "skills",
)

REQUIRED_LABEL_KEYS = (
    "facts", "languages", "certs", "core", "experience", "education",
    "publications", "projects", "skills", "verify", "link", "legend",
)


@dataclass
class Config:
    base_dir: Path
    person_name: str
    file_slug: str
    theme: str
    level_max: float
    languages: list[str]
    variants: list[str]
    documents: dict[str, list[str]]
    content: dict[str, Path]
    html_dir: Path
    pdf_dir: Path
    date_prefix: bool
    chrome: str | None


def _load_yaml(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"File not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    return raw


def _require(mapping: dict, key: str, where: str):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] is None:
        raise ConfigError(f"{where}: required field '{key}' is missing")
    return mapping[key]


def load_config(path: str | Path) -> Config:
    path = Path(path)
    raw = _load_yaml(path)
    base = path.parent

    person = _require(raw, "person", str(path))
    name = _require(person, "name", "person")
    slug = person.get("file_slug") or str(name).replace(" ", "-")

    languages = _require(raw, "languages", str(path))
    if not isinstance(languages, list) or not languages:
        raise ConfigError("languages: expected a non-empty list")

    variants = raw.get("variants") or ["default"]
    if not isinstance(variants, list):
        raise ConfigError("variants: expected a list of variant names")

    content_map = _require(raw, "content", str(path))
    for lang in languages:
        if lang not in content_map:
            raise ConfigError(f"content: no entry for language '{lang}'")

    documents_raw = raw.get("documents") or list(CANONICAL_DOCUMENTS)
    if isinstance(documents_raw, list):
        documents = {lang: list(documents_raw) for lang in languages}
    elif isinstance(documents_raw, dict):
        documents = {lang: list(documents_raw.get(lang) or CANONICAL_DOCUMENTS)
                     for lang in languages}
    else:
        raise ConfigError("documents: expected a list or a mapping per language")
    for lang, docs in documents.items():
        for doc in docs:
            if doc not in CANONICAL_DOCUMENTS:
                raise ConfigError(
                    f"documents[{lang}]: unknown document '{doc}' "
                    f"(allowed: {', '.join(CANONICAL_DOCUMENTS)})")

    output = raw.get("output") or {}
    return Config(
        base_dir=base,
        person_name=str(name),
        file_slug=str(slug),
        theme=str(raw.get("theme", "modern")),
        level_max=float(raw.get("level_max", 6)),
        languages=[str(lang) for lang in languages],
        variants=[str(v) for v in variants],
        documents=documents,
        content={lang: base / content_map[lang] for lang in languages},
        html_dir=base / output.get("html_dir", "html"),
        pdf_dir=base / output.get("pdf_dir", "pdf"),
        date_prefix=bool(output.get("date_prefix", True)),
        chrome=raw.get("chrome"),
    )


def load_content(path: str | Path) -> dict:
    path = Path(path)
    raw = _load_yaml(path)
    for key in REQUIRED_CONTENT_KEYS:
        _require(raw, key, str(path))
    labels = raw["labels"]
    for key in REQUIRED_LABEL_KEYS:
        _require(labels, key, f"{path}: labels")
    for key in CANONICAL_DOCUMENTS:
        _require(raw["doc_names"], key, f"{path}: doc_names")
    for cat in raw["skills"]:
        _require(cat, "category", f"{path}: skills")
        for item in _require(cat, "items", f"{path}: skills[{cat.get('category')}]"):
            _require(item, "name", f"{path}: skills[{cat['category']}]")
            _require(item, "level", f"{path}: skills[{cat['category']}]")
    return raw


def filter_facts(facts: list[dict], variant: str) -> list[dict]:
    """Filter the key facts down to one variant.

    A fact without a `variants` list appears in every variant; with the list
    it only appears in the variants named there. Order is preserved.
    """
    out = []
    for fact in facts:
        only = fact.get("variants")
        if only and variant not in only:
            continue
        out.append(fact)
    return out
