# Ergograph

**Ergograph** (Greek *ἔργον* "work, deed" + *γράφειν* "to write": "the one that writes down your work") is a YAML-driven CV and dossier generator. From plain content files it produces ready-to-send PDFs: a **CV**, a **project history**, a **skills matrix** and a **complete dossier**, in any number of languages and variants (e.g. with/without an hourly rate).

The generator contains **no personal data**. All content and all build steering come from the outside via YAML files; the code only provides rendering, the theme and the PDF export.

## How it works

```
config.yaml + content/<lang>.yaml  ->  HTML (theme "modern")  ->  PDF (Chrome headless)
```

1. `config.yaml` steers the build: person, languages, variants, documents, output paths.
2. One content file per language (`content/de.yaml`, `content/en.yaml`, …) with all texts, including section labels and document file names.
3. Chrome (headless) renders the HTML intermediate step to A4 PDFs; with PyMuPDF installed, the PDFs additionally get page numbers.

## Installation

Requirements: Python ≥ 3.10, Google Chrome or Chromium.

```bash
# install as a tool (recommended, with the page-numbers extra)
uv tool install "ergograph[pagenumbers] @ /path/to/ergograph"

# or run directly from the repo
uv run --project /path/to/ergograph ergograph --help
```

## Quick start

```bash
cd examples/
ergograph validate          # check config + content files
ergograph build             # build everything (HTML + PDF)
ergograph build --html-only # HTML only, no Chrome
ergograph build --variant mit-stundensatz --lang de
```

The PDFs end up under `pdf/<variant>/<language>/YYYY-MM-DD_<Name>_<document>_<language>.pdf`. Older builds are kept side by side thanks to the date prefix.

## The steering file `config.yaml`

```yaml
person:
  name: Alexandra Argyriou        # appears in the header and in the PDF file names
  # file_slug: Alexandra-Argyriou # optional, default: name with hyphens

theme: modern                     # bundled theme, or path to your own .css
level_max: 6                      # maximum of the skill-bar scale

languages: [de, en]
variants: [mit-stundensatz, ohne-stundensatz]

documents:                        # list (for all languages) or mapping per language
  de: [cv, projects, full]
  en: [full]

content:
  de: content/de.yaml
  en: content/en.yaml

output:
  html_dir: html
  pdf_dir: pdf
  date_prefix: true

# chrome: /path/to/chrome         # optional; otherwise auto-detected
```

## The content files

One YAML file per language with the sections `title`, `tagline`, `labels`, `doc_names`, `contact`, `facts`, `languages`, `certs`, `top_skills`, `education`, `experience`, `publications`, `projects` and `skills`. A complete, runnable example lives in [`examples/`](examples/); the format is specified in [`docs/SPEC.md`](docs/SPEC.md).

Variants are steered declaratively: an entry in `facts` with `variants: [mit-stundensatz]` only appears in that variant, all other facts appear everywhere.

```yaml
facts:
  - label: Availability
    value: from October 2026
  - label: Hourly rate
    value: €110-150/h depending on task
    variants: [mit-stundensatz]
```

Content values are trusted HTML fragments: write UTF-8 directly (ü, €, "…"), and use `<a href="...">…</a>` for inline links where needed.

## Tests

```bash
uv run pytest
```

## License

[MIT](LICENSE)
