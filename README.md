# Ergograph

[![CI](https://github.com/Supportlik/Ergograph/actions/workflows/ci.yml/badge.svg)](https://github.com/Supportlik/Ergograph/actions/workflows/ci.yml)
[![Security](https://github.com/Supportlik/Ergograph/actions/workflows/security.yml/badge.svg)](https://github.com/Supportlik/Ergograph/actions/workflows/security.yml)
[![PyPI](https://img.shields.io/pypi/v/ergograph.svg)](https://pypi.org/project/ergograph/)
[![Python versions](https://img.shields.io/pypi/pyversions/ergograph.svg)](https://pypi.org/project/ergograph/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Supportlik/Ergograph/blob/main/LICENSE)

**Ergograph** (Greek *ἔργον* "work, deed" + *γράφειν* "to write": "the one that writes down your work") is a YAML-driven CV and dossier generator. From plain content files it produces ready-to-send PDFs: a **CV**, a **project history**, a **skills matrix** and a **complete dossier**, in any number of languages and variants (e.g. with/without an hourly rate).

The generator contains **no personal data**. All content and all build steering come from the outside via YAML files; the code only provides rendering, the theme and the PDF export.

## How it works

```
config.yaml + content/<lang>.yaml  ->  HTML (theme "modern")  ->  PDF (Chrome headless)
```

1. `config.yaml` steers the build: person, languages, variants, documents, output paths.
2. One content file per language (`content/de.yaml`, `content/en.yaml`, …) with all texts, including section labels and document file names.
3. Chrome (headless) renders the HTML intermediate step to A4 PDFs, which then get page numbers and title/author metadata stamped in.

## Installation

Requirements: Python ≥ 3.10 and Google Chrome or Chromium. Chrome is only needed for
the PDF step (`ergograph build --html-only` works without it) and is not installed by
pip — Ergograph looks for an existing installation (see `chrome:` below).

```bash
# as an isolated tool (recommended)
uv tool install ergograph

# or into the current environment
pip install ergograph
```

There are no extras to pick: page numbers and the ATS check are always included.
Both dependencies (PyYAML and pypdf) are pure Python and together under 1 MB.

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

The rendered example PDFs are committed per persona under `examples/<name>/pdf/`, e.g. the [German CV](https://github.com/Supportlik/Ergograph/blob/main/examples/minimal/pdf/mit-stundensatz/de/Alexandra-Argyriou_lebenslauf_de.pdf) or the [comprehensive architect dossier](https://github.com/Supportlik/Ergograph/blob/main/examples/software-architect/pdf/mit-stundensatz/de/Daniel-Falkner_dossier-komplett_de.pdf).

## ATS readability

The documents are built to be fully readable by applicant tracking systems: a real text layer (no text in images), reading order equal to content order, skill levels as numbers next to the bars, and PDF title/author metadata. Ergograph verifies this instead of assuming it — after every build it extracts the PDF text layer (pypdf, the same way ATS parsers read PDFs) and asserts that **every** content string from your YAML appears in it. Findings are reported as warnings; `ergograph build --strict` turns them into a build failure. Details in [`docs/SPEC.md`](https://github.com/Supportlik/Ergograph/blob/main/docs/SPEC.md) (R15/D13).

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

Every field with its type, default and whether it is required: [`docs/CONFIGURATION.md`](https://github.com/Supportlik/Ergograph/blob/main/docs/CONFIGURATION.md).

## The content files

One YAML file per language holds everything that appears in the documents. The
picture shows which key renders which region — red comes from
`content/<lang>.yaml`, green are the headings from `labels`, and blue is the one
visible field that comes from `config.yaml`:

![Annotated CV showing which YAML key renders which region](https://raw.githubusercontent.com/Supportlik/Ergograph/main/docs/images/content-keys.png)

| # | Key | Type | Renders |
|---|---|---|---|
| A | `person.name` (config) | string | Name in the header |
| 1 | `title` | string | Job title under the name |
| 2 | `contact` | list of `{label, value, url?}` | Header line |
| 3 | `tagline` | string | Summary paragraph |
| 4 | `facts` | list of `{label, value, variants?}` | Sidebar: availability, rate, … |
| 5 | `languages` | list of `{name, level}` | Sidebar: language skills |
| 6 | `certs` | list of `{name, description?, url?}` | Sidebar: certificates |
| 7 | `top_skills` | list of strings | Sidebar: competency tags |
| 8 | `experience` | list of `{period, role, org, bullets}` | Stations with bullets |
| 9 | `education` | list of `{year, degree, institution}` | Degrees |
| 10 | `publications` | list of `{title, venue, url?, summary?}` | Publication list |
| 11 | `labels` | map of 12 headings | Every heading in both columns |

Three keys are not visible above: `projects` builds the project history, `skills`
the skills matrix, and `doc_names` supplies the PDF file names. All fourteen keys
are required, but **every list may be empty** — `publications: []` simply drops
that section, which is how one format serves a software architect and a carpenter.

Variants are steered declaratively: a fact carrying `variants` appears only in
those variants, everything else appears everywhere.

```yaml
facts:
  - label: Availability
    value: immediately
  - label: Hourly rate
    value: €100/h
    variants: [mit-stundensatz]
```

Content values are trusted HTML fragments: write UTF-8 directly (ü, €, "…"), and
use `<a href="...">…</a>` for inline links where needed.

**Full field reference — every field, its type, whether it is required and its
default: [`docs/CONFIGURATION.md`](https://github.com/Supportlik/Ergograph/blob/main/docs/CONFIGURATION.md).** The repository
also ships [JSON Schemas](https://github.com/Supportlik/Ergograph/blob/main/schemas/) for both file types, so an editor can
complete fields and flag typos while you write.

## Generating content with an AI agent

The content files are plain, flat YAML with every text outside the code, which
makes them a practical target for an agentic coding tool (Claude Code, Codex,
Cursor, …): the agent gets a machine-readable contract in
[`schemas/`](https://github.com/Supportlik/Ergograph/blob/main/schemas/), working examples, and two commands that judge the
result objectively — `ergograph validate` for the structure and
`ergograph build --strict`, which fails when a string from the YAML is not
extractable from the finished PDF. That turns "write my CV data" into a loop the
agent can close by itself.

A ready-to-use prompt, plus what to check by hand afterwards (numbers, dates,
certificate titles — a model formats reliably and invents plausibly), is in
[`docs/CONFIGURATION.md`](https://github.com/Supportlik/Ergograph/blob/main/docs/CONFIGURATION.md#generating-content-with-an-ai-agent).

## Examples

Every example under [`examples/`](https://github.com/Supportlik/Ergograph/blob/main/examples/) is a fictional persona and ships with its rendered PDFs:

| Example | Shows |
|---|---|
| [`minimal`](https://github.com/Supportlik/Ergograph/blob/main/examples/minimal/) | Small bilingual dossier with rate variants — also the test fixture |
| [`software-architect`](https://github.com/Supportlik/Ergograph/blob/main/examples/software-architect/) | Comprehensive bilingual freelance dossier: structured bullets, project `period`/`org` metadata, publications with summaries |
| [`handwerker`](https://github.com/Supportlik/Ergograph/blob/main/examples/handwerker/) | Master carpenter — trade CV with certificates and reference projects, no publications |
| [`reporter`](https://github.com/Supportlik/Ergograph/blob/main/examples/reporter/) | Journalist — publications with summaries, investigative projects |
| [`arzt`](https://github.com/Supportlik/Ergograph/blob/main/examples/arzt/) | Physician — clinical-academic CV with board certifications and studies |
| [`buerokauffrau`](https://github.com/Supportlik/Ergograph/blob/main/examples/buerokauffrau/) | Office administrator — commercial CV with internal projects |

Variants are steered declaratively: an entry in `facts` with `variants: [mit-stundensatz]` only appears in that variant, all other facts appear everywhere.

```yaml
facts:
  - label: Availability
    value: immediately
```

Content values are trusted HTML fragments: write UTF-8 directly (ü, €, "…"), and use `<a href="...">…</a>` for inline links where needed.

## Development

```bash
uv run pytest                    # test suite, no Chrome and no network needed
uvx pip-audit -r <(uv export --format requirements-txt --all-extras --no-dev --no-emit-project)
trivy fs --scanners vuln,secret,misconfig .
```

Every push runs the suite on Python 3.10–3.14, renders all examples, and scans
dependencies and sources (pip-audit, Trivy, CodeQL). Releases go to PyPI from a `v*`
tag via trusted publishing. Version history: [`CHANGELOG.md`](https://github.com/Supportlik/Ergograph/blob/main/CHANGELOG.md).

## License

[MIT](https://github.com/Supportlik/Ergograph/blob/main/LICENSE)
