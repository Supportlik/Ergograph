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
cd examples/minimal/
ergograph validate          # check config + content files
ergograph build             # build everything (HTML + PDF)
ergograph build --html-only # HTML only, no Chrome
ergograph build --variant mit-stundensatz --lang de
```

The PDFs end up under `pdf/<variant>/<language>/YYYY-MM-DD_<Name>_<document>_<language>.pdf`. Older builds are kept side by side thanks to the date prefix (disable it with `output.date_prefix: false`).

## Example output

The rendered example PDFs are committed per persona under `examples/<name>/pdf/`, e.g. the [German CV](examples/minimal/pdf/mit-stundensatz/de/Alexandra-Argyriou_lebenslauf_de.pdf) or the [comprehensive architect dossier](examples/software-architect/pdf/mit-stundensatz/de/Daniel-Falkner_dossier-komplett_de.pdf).

## ATS readability

The documents are built to be fully readable by applicant tracking systems: a real text layer (no text in images), reading order equal to content order, skill levels as numbers next to the bars, and PDF title/author metadata. Ergograph verifies this instead of assuming it — after every build it extracts the PDF text layer (PyMuPDF, the same way ATS parsers read PDFs) and asserts that **every** content string from your YAML appears in it. Findings are reported as warnings; `ergograph build --strict` turns them into a build failure. Details in [`docs/SPEC.md`](docs/SPEC.md) (R15/D13).

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
  date_prefix: true    # date-stamped file names; false = stable names

# chrome: /path/to/chrome         # optional; otherwise auto-detected
```

## The content files

One YAML file per language with the sections `title`, `tagline`, `labels`, `doc_names`, `contact`, `facts`, `languages`, `certs`, `top_skills`, `education`, `experience`, `publications`, `projects` and `skills`. Empty lists hide the corresponding section. The format is specified in [`docs/SPEC.md`](docs/SPEC.md).

## Examples

Every example under [`examples/`](examples/) is a fictional persona and ships with its rendered PDFs:

| Example | Shows |
|---|---|
| [`minimal`](examples/minimal/) | Small bilingual dossier with rate variants — also the test fixture |
| [`software-architect`](examples/software-architect/) | Comprehensive bilingual freelance dossier: structured bullets, project `period`/`org` metadata, publications with summaries |
| [`handwerker`](examples/handwerker/) | Master carpenter — trade CV with certificates and reference projects, no publications |
| [`reporter`](examples/reporter/) | Journalist — publications with summaries, investigative projects |
| [`arzt`](examples/arzt/) | Physician — clinical-academic CV with board certifications and studies |
| [`buerokauffrau`](examples/buerokauffrau/) | Office administrator — commercial CV with internal projects |

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
