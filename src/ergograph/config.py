"""Loading and validating the steering config and the content files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Error in the config.yaml or in a content file."""


#: Canonical document keys; localized file names come from `doc_names`
#: in the respective content file.
CANONICAL_DOCUMENTS = ("cv", "projects", "skills", "full", "onepager")

#: Documents built when `documents:` is left out. The one-pager is opt-in,
#: because it needs its own `onepager:` block in every content file.
DEFAULT_DOCUMENTS = ("cv", "projects", "skills", "full")

#: Output formats that can be requested via `formats:` in the config.
#: HTML is always written, because it is the intermediate step of the PDF route.
CANONICAL_FORMATS = ("pdf", "docx", "md")

#: Image types a photo may have; the PDF and the DOCX embed the file as is.
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

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
class VariantSpec:
    """One build variant. `tags` always contains the variant's own name;
    an anonymous variant additionally carries the tag `anonymous`."""
    name: str
    tags: frozenset[str]
    anonymous: bool = False
    documents: list[str] | None = None
    photo: bool = True
    #: documents of this variant that go into flat_dir (None: output.flat_documents)
    flat_documents: list[str] | None = None
    #: name part in flat file names (None: the variant name, "": none)
    flat_label: str | None = None


@dataclass
class PhotoSpec:
    file: Path
    documents: list[str]
    languages: list[str] | None
    files: dict[str, Path]

    def for_document(self, document: str, lang: str) -> Path | None:
        if document not in self.documents:
            return None
        if self.languages is not None and lang not in self.languages:
            return None
        return self.files.get(document, self.file)


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
    docx_dir: Path
    md_dir: Path
    flat_dir: Path | None
    flat_documents: list[str] | None
    flat_by_format: bool
    formats: list[str]
    date_prefix: bool
    chrome: str | None
    docx_font: str
    variant_specs: dict[str, VariantSpec] = field(default_factory=dict)
    photo: PhotoSpec | None = None
    anonymous_slug: str = "profile"

    def spec(self, variant: str) -> VariantSpec:
        return self.variant_specs.get(variant) or VariantSpec(
            variant, frozenset({variant}))

    def documents_for(self, variant: str, lang: str) -> list[str]:
        docs = self.documents[lang]
        only = self.spec(variant).documents
        return [d for d in docs if d in only] if only is not None else docs


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

    variant_specs = _load_variants(raw.get("variants") or ["default"])
    variants = list(variant_specs)

    content_map = _require(raw, "content", str(path))
    for lang in languages:
        if lang not in content_map:
            raise ConfigError(f"content: no entry for language '{lang}'")

    documents_raw = raw.get("documents") or list(DEFAULT_DOCUMENTS)
    if isinstance(documents_raw, list):
        documents = {lang: list(documents_raw) for lang in languages}
    elif isinstance(documents_raw, dict):
        documents = {lang: list(documents_raw.get(lang) or DEFAULT_DOCUMENTS)
                     for lang in languages}
    else:
        raise ConfigError("documents: expected a list or a mapping per language")
    for lang, docs in documents.items():
        for doc in docs:
            if doc not in CANONICAL_DOCUMENTS:
                raise ConfigError(
                    f"documents[{lang}]: unknown document '{doc}' "
                    f"(allowed: {', '.join(CANONICAL_DOCUMENTS)})")

    formats_raw = raw.get("formats") or ["pdf"]
    if not isinstance(formats_raw, list) or not formats_raw:
        raise ConfigError("formats: expected a non-empty list")
    formats = [str(f) for f in formats_raw]
    for fmt in formats:
        if fmt not in CANONICAL_FORMATS:
            raise ConfigError(
                f"formats: unknown format '{fmt}' "
                f"(allowed: {', '.join(CANONICAL_FORMATS)})")

    for spec in variant_specs.values():
        for doc in spec.documents or []:
            if doc not in CANONICAL_DOCUMENTS:
                raise ConfigError(
                    f"variants[{spec.name}].documents: unknown document '{doc}' "
                    f"(allowed: {', '.join(CANONICAL_DOCUMENTS)})")

    photo = _load_photo(raw.get("photo"), base, languages)

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
        docx_dir=base / output.get("docx_dir", "docx"),
        md_dir=base / output.get("md_dir", "md"),
        flat_dir=(base / output["flat_dir"]) if output.get("flat_dir") else None,
        flat_documents=_flat_documents(output.get("flat_documents")),
        flat_by_format=bool(output.get("flat_by_format", False)),
        formats=formats,
        date_prefix=bool(output.get("date_prefix", True)),
        chrome=raw.get("chrome"),
        docx_font=str(output.get("docx_font", "Segoe UI")),
        variant_specs=variant_specs,
        photo=photo,
        anonymous_slug=str(person.get("anonymous_slug") or "profile"),
    )


def _flat_documents(raw) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ConfigError("output.flat_documents: expected a list of documents")
    for doc in raw:
        if doc not in CANONICAL_DOCUMENTS:
            raise ConfigError(f"output.flat_documents: unknown document '{doc}'")
    return [str(d) for d in raw]


def _load_variants(raw) -> dict[str, VariantSpec]:
    """`variants` is either a list of names (every variant is just its name)
    or a mapping name -> options {tags, anonymous, documents, photo}."""
    if isinstance(raw, list):
        return {str(v): VariantSpec(str(v), frozenset({str(v)})) for v in raw}
    if not isinstance(raw, dict) or not raw:
        raise ConfigError("variants: expected a list of variant names "
                          "or a mapping name -> options")
    specs = {}
    for name, opts in raw.items():
        name = str(name)
        opts = opts or {}
        if not isinstance(opts, dict):
            raise ConfigError(f"variants[{name}]: expected a mapping of options")
        unknown = set(opts) - {"tags", "anonymous", "documents", "photo",
                               "flat_documents", "flat_label"}
        if unknown:
            raise ConfigError(f"variants[{name}]: unknown option(s) "
                              f"{', '.join(sorted(unknown))}")
        anonymous = bool(opts.get("anonymous", False))
        tags = {name, *(str(t) for t in opts.get("tags") or [])}
        if anonymous:
            tags.add("anonymous")
        docs = opts.get("documents")
        if docs is not None and not isinstance(docs, list):
            raise ConfigError(f"variants[{name}].documents: expected a list")
        flat_docs = opts.get("flat_documents")
        if flat_docs is not None:
            flat_docs = _flat_documents(flat_docs)
        label = opts.get("flat_label")
        specs[name] = VariantSpec(
            name, frozenset(tags), anonymous,
            [str(d) for d in docs] if docs is not None else None,
            bool(opts.get("photo", True)) and not anonymous,
            flat_docs, None if label is None else str(label))
    return specs


def _photo_path(value, base: Path, where: str) -> Path:
    path = Path(str(value)).expanduser()
    path = path if path.is_absolute() else base / path
    if path.suffix.lower() not in PHOTO_TYPES:
        raise ConfigError(f"{where}: unsupported image type '{path.suffix}' "
                          f"(allowed: {', '.join(PHOTO_TYPES)})")
    if not path.is_file():
        raise ConfigError(f"{where}: file not found: {path}")
    return path


def _load_photo(raw, base: Path, languages: list) -> PhotoSpec | None:
    """`photo` is a path, or {file, documents?, languages?, files?}."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = {"file": raw}
    if not isinstance(raw, dict):
        raise ConfigError("photo: expected a path or a mapping")
    file = _photo_path(_require(raw, "file", "photo"), base, "photo.file")
    docs = [str(d) for d in raw.get("documents") or ("cv", "full", "onepager")]
    for doc in docs:
        if doc not in CANONICAL_DOCUMENTS:
            raise ConfigError(f"photo.documents: unknown document '{doc}'")
    langs = raw.get("languages")
    if langs is not None:
        langs = [str(lang) for lang in langs]
        for lang in langs:
            if lang not in languages:
                raise ConfigError(f"photo.languages: unknown language '{lang}'")
    files = {}
    for doc, value in (raw.get("files") or {}).items():
        if doc not in CANONICAL_DOCUMENTS:
            raise ConfigError(f"photo.files: unknown document '{doc}'")
        files[str(doc)] = _photo_path(value, base, f"photo.files.{doc}")
    return PhotoSpec(file, docs, langs, files)


def load_content(path: str | Path) -> dict:
    path = Path(path)
    raw = _load_yaml(path)
    for key in REQUIRED_CONTENT_KEYS:
        _require(raw, key, str(path))
    labels = raw["labels"]
    for key in REQUIRED_LABEL_KEYS:
        _require(labels, key, f"{path}: labels")
    for key in DEFAULT_DOCUMENTS:
        _require(raw["doc_names"], key, f"{path}: doc_names")
    for cat in raw["skills"]:
        _require(cat, "category", f"{path}: skills")
        for item in _require(cat, "items", f"{path}: skills[{cat.get('category')}]"):
            _require(item, "name", f"{path}: skills[{cat['category']}]")
            _require(item, "level", f"{path}: skills[{cat['category']}]")
    return raw


def check_documents(content: dict, documents: list[str], path) -> None:
    """Checks that only apply when a document is actually built: the
    one-pager needs its own block, a file name and resolvable references."""
    if "onepager" not in documents:
        return
    where = f"{path}: onepager"
    _require(content["doc_names"], "onepager", f"{path}: doc_names")
    block = _require(content, "onepager", str(path))
    labels = _require(block, "labels", where)
    for key in ("competencies", "projects", "timeline"):
        _require(labels, key, f"{where}.labels")
    ids = {item.get("id") for group in content["projects"]
           for item in group["items"] if item.get("id")}
    for index, entry in enumerate(block.get("projects") or []):
        ref = entry.get("ref")
        if ref is not None and ref not in ids:
            raise ConfigError(f"{where}.projects[{index}]: unknown ref '{ref}' "
                              f"(no project item has this id)")
        if ref is None:
            _require(entry, "title", f"{where}.projects[{index}]")
    for index, cluster in enumerate(block.get("competencies") or []):
        _require(cluster, "name", f"{where}.competencies[{index}]")
    for index, station in enumerate(block.get("timeline") or []):
        _require(station, "period", f"{where}.timeline[{index}]")
        _require(station, "label", f"{where}.timeline[{index}]")


def filter_facts(facts: list[dict], variant: str) -> list[dict]:
    """Filter the key facts down to one variant (kept for compatibility;
    the builder resolves the whole content tree via `variants.resolve`)."""
    from .variants import resolve
    return resolve(facts, frozenset({variant}))
