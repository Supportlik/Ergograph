# Ergograph – Specification

As of: 2026-08-20 · Version 1.0.0

This document records all requirements as they were implemented and justifies the central design decisions. It deliberately lives next to the code and is updated with every substantial change.

## 1. Background

Ergograph is the decoupling of a previously monolithic build script (`build.py` in a private knowledge vault, as of 2026-08) in which content, layout and build logic were mixed into a single file. Goals of the decoupling: an independent version history for the generator, reusability, and content that is steered exclusively from the outside via YAML.

## 2. Requirements and their implementation

| No. | Requirement | Implementation |
|---|---|---|
| R1 | Content fully steerable from the outside via YAML; the generator contains no personal data. | One content file per language (`content/<lang>.yaml`) with all texts incl. section labels (`labels`) and localized document names (`doc_names`). Loading/validation in `config.py:load_content`. The repo only ships fictional example content (`examples/`). |
| R2 | Build steering (languages, variants, documents, output paths, theme) also via YAML. | Central `config.yaml`, parsed by `config.py:load_config` into a `Config` dataclass. All paths are relative to the location of the `config.yaml`. |
| R3 | Four document types: CV, project history, skills matrix, complete dossier. | Canonical keys `cv`, `projects`, `skills`, `full` (`config.py:CANONICAL_DOCUMENTS`); composition in `render.py:build_documents`. `full` = cv + page break + projects + page break + skills. |
| R4 | Multilingualism (at least DE/EN), extensible without code changes. | Languages are just keys in `config.yaml` (`languages` + `content` mapping). Every additional language = one additional content file. There is no language-specific logic in the code (see D6). |
| R5 | Variants (e.g. with/without hourly rate) without code changes. | Declarative filtering: a `facts` entry with `variants: [a, b]` only appears in variants a and b; without the attribute it appears everywhere (`config.py:filter_facts`). Variant names are free-form. |
| R6 | Selection of the documents to build, steerable per language. | `documents` in the config: flat list (applies to all languages) or mapping per language. |
| R7 | PDF export in A4, file names carrying date, name slug, document name and language code. | Chrome headless (`pdf.py:render_pdf`), file names via `builder.py:pdf_filename` → `YYYY-MM-DD_<slug>_<document>_<lang>.pdf`. Date prefix can be disabled via `output.date_prefix` and overridden via `--date`. |
| R8 | Page numbers in the PDF, without pulling in a heavy dependency. | `pdf.py:finalize_pdf` stamps 'i / n' centered at the bottom of every page using pypdf (pure Python, 374 kB) and a PDF base-14 Helvetica, so nothing needs embedding (see D9). |
| R9 | CLI with validation and selective building. | `ergograph validate` (config + all content files), `ergograph build` with `--variant`, `--lang`, `--html-only`, `--date`, `-c/--config`. Errors exit with code 1 and a clear error message. |
| R10 | Clear error messages for broken input files. | Dedicated `ConfigError` exception; required fields are checked at load time (top-level keys, `labels`, `doc_names`, skill entries) and reported with file/field context. |
| R11 | Exchangeable themes. | `theme:` accepts the name of a bundled theme (`modern`) or the path to a custom `.css` file (`render.py:load_theme`). |
| R12 | Chrome path configurable and portable (macOS/Windows/Linux). | Search order: `chrome:` in the config → environment variable `ERGOGRAPH_CHROME` → well-known installation paths → `PATH` (`pdf.py:find_chrome`). |
| R13 | Tests that run without Chrome and without network access. | Pytest suite under `tests/` against the example content: config/content validation, variant filter, HTML rendering, file names. PDF rendering is deliberately not tested (see D8). |
| R14 | Output parity with the replaced `build.py`. | During the migration, the generated HTML was compared byte-for-byte (after entity-decoding the legacy output) against the last outputs of the old script. The HTML structure and the CSS theme `modern` were taken over unchanged. |
| R15 | The documents must be fully readable by applicant tracking systems (ATS): every piece of content machine-extractable from the PDF text layer. | Structural guarantees: real text layer (Chrome print-to-PDF, no images of text), reading order = DOM order, skill levels also as numbers next to the bars, PDF title/author metadata (`pdf.py:finalize_pdf`). Automatic verification after every build: `ats.py` extracts the PDF text (pypdf) and asserts that ALL content strings from the YAML appear in it; findings are logged as warnings, `--strict` turns them into a build failure (see D13). |
| R16 | The rendered example output ships in the repo. | `examples/<persona>/pdf/` is committed (see `.gitignore`); the example configs use `date_prefix: false` so file names stay stable across re-renders. The examples are rebuilt with `ergograph build --strict` inside each persona folder whenever the format or theme changes. They are excluded from the sdist, where they would only add weight (see `[tool.hatch.build.targets.sdist]`). |
| R17 | Every change is verified automatically on the supported Python versions. | `.github/workflows/ci.yml`: the pytest suite on Python 3.10–3.14, plus `ergograph validate` and `ergograph build --html-only` for every persona under `examples/` (no Chrome in CI, see D8). A second job builds sdist + wheel, runs `twine check --strict` and asserts that `ergograph.__version__` equals the installed package metadata. |
| R18 | Published code is scanned for known vulnerabilities, leaked secrets and misconfigurations. | `.github/workflows/security.yml`, on every push, every pull request and weekly: `pip-audit` against the locked runtime set exported from `uv.lock`, Trivy (`vuln,secret,misconfig`), CodeQL (`security-and-quality`), and `dependency-review` on pull requests. Results go to GitHub code scanning; HIGH/CRITICAL findings fail the build. Dependabot proposes weekly dependency and action updates. |
| R19 | Installable from PyPI, released reproducibly from a tag. | Packaging metadata (classifiers, project URLs, PEP 639 license expression) in `pyproject.toml`; `.github/workflows/release.yml` triggers on `v*` tags, runs the tests, builds, refuses to publish if the tag does not match the built version, then publishes via PyPI trusted publishing (see D17) and creates the GitHub release. |
| R20 | The file formats are documented field by field, and an editor can check them while writing. | `docs/CONFIGURATION.md` lists every field of both file types with type, required flag, default and the region it renders, anchored by an annotated screenshot (`docs/images/content-keys.png`, regenerated by `docs/tools/annotate_content_map.py`). `schemas/config.schema.json` and `schemas/content.schema.json` (JSON Schema 2020-12) give editors completion and typo detection; `tests/test_schemas.py` validates every bundled example against them (see D18). |
| R21 | The examples are fictional and must not overlap with the author's real dossier. | The personas are invented; `software-architect` was originally derived from the author's own dossier and was decoupled in the 1.0.0 follow-up: certificates, role titles, capacity statements, project group names and skill notes were replaced after a field-wise comparison against the private dossier, down to zero matching values across all eight content files. The comparison ran outside the repo; no real value is recorded here.
| R22 | Content files can be produced by AI agents, with a documented workflow. | The format is flat YAML with named keys and no templating, so an agent has a contract (`schemas/`), a reference (`docs/CONFIGURATION.md`) and working examples. Two commands close the loop objectively: `validate` reports the offending field, and `build --strict` fails when a YAML string is not extractable from the PDF (R15), so correctness is checkable instead of merely plausible. `docs/CONFIGURATION.md` carries a prompt template that forbids inventing facts, plus the review checklist for what a model tends to smooth over (numbers, dates, certificate titles).

## 3. Formats

### 3.1 `config.yaml`

| Field | Required | Meaning |
|---|---|---|
| `person.name` | yes | Name in the document header and (as a slug) in the PDF file names |
| `person.file_slug` | no | Slug for file names; default: name with `-` instead of spaces |
| `theme` | no | `modern` (default) or path to a custom `.css` |
| `level_max` | no | Maximum of the skill-bar scale (default 6) |
| `languages` | yes | List of language codes |
| `variants` | no | List of variant names (default `[default]`) |
| `documents` | no | List or mapping per language; subset of `cv, projects, skills, full` (default: all) |
| `content` | yes | Mapping language code → path of the content file |
| `output.html_dir` / `output.pdf_dir` | no | Output directories (default `html` / `pdf`) |
| `output.date_prefix` | no | Date prefix in PDF names (default `true`) |
| `chrome` | no | Explicit Chrome path |

### 3.2 Content file (per language)

Required keys: `title`, `tagline`, `labels`, `doc_names`, `contact`, `facts`, `languages`, `certs`, `top_skills`, `education`, `experience`, `publications`, `projects`, `skills`. Lists may be empty — an empty list hides the corresponding section or sidebar block (e.g. `publications: []` for professions without publications).

- `labels`: all section headings and small texts (`facts`, `languages`, `certs`, `core`, `experience`, `education`, `publications`, `projects`, `skills`, `verify`, `link`, `legend`).
- `doc_names`: localized file names for `cv`, `projects`, `skills`, `full` (e.g. `cv: lebenslauf`).
- `contact`: list of `{label, value, url?}`.
- `facts`: list of `{label, value, variants?}`; order = display order.
- `languages`: list of `{name, level}` (the person's language skills).
- `certs`: list of `{name, description?, url?}`; with `url` a proof link is rendered.
- `education`: list of `{year, degree, institution}`.
- `experience`: list of `{period, role, org, bullets}`; each bullet is a plain string or `{text, org?, period?}` — `period` renders right-aligned next to the text, `org` as a small subtitle line below (e.g. per-project client entries inside a freelance station).
- `publications`: list of `{title, venue, url?, summary?}`; `summary` is one sentence on what the publication covers, rendered after the venue in the CV part.
- `projects`: list of `{group, meta, items: [{title, period?, org?, description, tech}]}`; `description` is a string or a list of paragraphs. `period` renders right-aligned next to the item title, `org` (client/department) as a subtitle below it; both are optional and purely additive.
- `skills`: list of `{category, items: [{name, level, note?}]}`; `level` is a number on the scale up to `level_max`.

## 4. Design decisions

**D1 – YAML instead of Python data structures.** Content is data, not a program. YAML is diff-friendly, supports comments and can be edited safely by non-developers (and LLM tooling). JSON was ruled out for its lack of comments and poor readability of long texts, TOML for its unwieldy nested lists.

**D2 – Content values are trusted HTML fragments.** Values are inserted into the HTML without escaping. This allows inline links (`<a href>`) and fine typography directly in the content and keeps the code free of an intermediate markup language. This is deliberately not a tool for foreign/untrusted input; the content lives locally with the user. Consequence: write UTF-8 directly (ü, €, "…"); HTML entities are unnecessary.

**D3 – Paragraphs as YAML lists.** The old script separated paragraphs in project descriptions with a `||` marker inside a single string. Now `description` is either a string or a list of paragraphs; the marker is gone without replacement.

**D4 – Variants as a declarative attribute instead of code.** The old script inserted the hourly-rate fact at a fixed position via code. Now the fact sits at its desired position in the list and carries a `variants` attribute; filtering preserves order. Currently the attribute applies to `facts`; should variant steering become necessary in other sections, `filter_facts` is the single extension point.

**D5 – Labels and document names belong to the content.** `labels` and `doc_names` live in the content file, not in the code: a new language therefore requires zero code changes, and the translation of all visible texts lives in one place.

**D6 – No language-specific logic in the renderer.** The old script converted German quotation marks for EN at render time (`&bdquo;` → `&ldquo;`). Now every content file writes its own typography; the renderer treats all languages identically. The conversion happened once during the migration of the legacy content.

**D7 – Chrome headless instead of a Python PDF library.** Decision kept from the old system: the HTML/CSS route gives pixel-exact control over the layout (grid, print CSS, web fonts) and Chrome is present on developer machines anyway. WeasyPrint & co. would have brought a heavy native dependency chain and endangered the existing, proven CSS theme.

**D8 – Tests without Chrome and without network access.** Everything deterministic is tested: loading, validation, filtering, HTML composition, file names. The Chrome invocation itself is a thin, stable subprocess line; testing it would mean installing Chrome in CI, which the benefit does not justify. The example content under `examples/` doubles as test fixtures so it can never go stale.

**D9 – Page numbers and text extraction via pypdf, as a regular dependency (since 1.0.0).** Chrome headless cannot produce custom headers/footers with page numbers in the desired style, so they are stamped afterwards. Until 0.5.0 this was PyMuPDF behind the extra `ergograph[pagenumbers]`, because PyMuPDF is an 18-23 MB binary wheel. The extra was the wrong trade: without it the PDFs lost their page numbers *and* the ATS check of R15 silently skipped — the default installation did not deliver the tool's central promise. pypdf does both jobs in 374 kB of pure Python: `finalize_pdf` stamps the number as a content-stream fragment in base-14 Helvetica (measured from the built-in advance widths, so no font file and no embedding is needed), and `extract_text` reads the text layer for the ATS check. Verified during the switch: identical stamp geometry (same position to 0.1 pt, 0 differing pixels at 150 dpi across the example dossiers), identical ATS result (1,639 expected strings across 18 example PDFs, 0 missing with either library), and 0.3 % larger files. Consequence for the implementation: the page content must be wrapped in `q`/`Q` before appending the stamp, because Chrome emits a global `cm` transformation with no enclosing `q` that would otherwise scale and mirror the stamp along with the page.

**D10 – Date prefix in file names instead of overwriting.** Kept from the old system: older builds remain side by side and stay distinguishable. Via `--date` the stamp can be pinned for reproducible builds.

**D11 – `src` layout, Hatchling, `uv`-friendly.** Standard Python packaging (PEP 621) with `src` layout against accidental imports from the working directory; the only runtime dependency is PyYAML. Console script `ergograph`.

**D12 – MIT license.** The code is generic and contains no business data; MIT maximizes reusability at minimal overhead and is the de-facto standard for small portfolio tools.

**D13 – ATS readability is verified, not assumed.** "ATS-readable" here means: an applicant tracking system that parses the PDF text layer (the common case) receives every piece of content. After each rendered PDF, `ats.py:key_strings` collects ALL content strings of the built document (name, contact, facts, roles, periods, bullets, project descriptions, tech lines, skills, labels, …) and `missing_strings` asserts each one appears in the text extracted with pypdf — the same way ATS parsers read PDFs. The comparison normalizes both sides identically, so it stays strict while tolerating three extraction artifacts that do not affect real parsers: CSS `text-transform: uppercase` (case folding), line wraps after hyphens ("Cloud-\nInfrastruktur"), and the generator's own page-number stamps between pages (stripped before matching). Limits, stated honestly: this proves machine-extractability and ordering, not the ranking behavior of any specific commercial ATS; and in an install stripped of pypdf (`pip install --no-deps`) the check is skipped (the structural guarantees of R15 still hold). Verified against the author's production dossier: 1,488 content strings across 8 PDFs, 0 missing.

**D14 – Layout refinements (0.3.0), based on an external design review.** Four changes to the `modern` theme and the document composition: (a) briefly, CV and project history flowed into each other in the combined dossier; since 0.5.0 every part starts on its own page again (owner preference — the parts read as chapters). The `SECTION_GAP` spacer and its CSS remain available. (b) The project-history typography now matches the CV part (body 10.2px instead of 9.2px) and its line length is capped at 165mm. (c) The skills matrix renders in two CSS columns (`.skills-cols`), roughly halving its footprint. (d) Break rules: a section heading never sits alone at a page end (`h2.section { break-after: avoid }`), and a project group keeps its header together with its first project. This deliberately supersedes the pixel parity of R14 — parity was a migration-time guarantee, not a design freeze.

**D15 – One single version stamp.** The version lives in `src/ergograph/__init__.py`; `pyproject.toml` declares `dynamic = ["version"]` and Hatchling reads it from there. Before 1.0.0 the number was maintained in both files and drifted: 0.4.0 and 0.5.0 were released while `pyproject.toml` still said 0.3.4, so a `pip install`ed package reported the wrong version. CI additionally compares `__version__` against the built metadata, and a release refuses a tag that does not match the artifact.

**D16 – `uv.lock` is committed.** For a pure library a lockfile is optional, but Ergograph also ships a CLI and is scanned: `uv sync --locked` makes CI runs reproducible, and pip-audit and Trivy can only audit the exact dependency set users get if that set is written down. It does not constrain consumers — `pip install ergograph` still resolves against the ranges in `pyproject.toml`.

**D17 – Trusted publishing instead of an API token.** The release workflow authenticates to PyPI via OIDC (`id-token: write`, environment `pypi`). No long-lived token exists in the repository secrets, so there is nothing to leak or rotate; PyPI verifies the workflow identity instead. Consequence: releases only ever happen through the workflow, which is intended — a manual `twine upload` from a laptop would bypass the test gate.

**D18 – JSON Schemas for editors, the loader stays the authority.** The schemas in `schemas/` exist so an editor can complete field names and flag typos while a content file is being written. They are deliberately *not* used at runtime: validation stays in `config.py`, which reports one problem at a time with file and field context (R10) instead of a schema library's paths, and the package keeps its two pure-Python dependencies. The risk of a second description of the same format is drift, so `tests/test_schemas.py` validates all bundled examples against the schemas, plus one negative case; since the examples are also the test fixtures (D8), a format change that misses the schemas fails the suite.

## 5. Out of scope (deliberately not implemented)

- **No photo support, no additional sections via configuration.** The section structure (contact, facts, …, skills) is hard-wired; new sections are a code change. A generic "section construction kit" schema would be considerably more complex and will only be built once it is needed.
- **No HTML escaping / no sanitization** (see D2).
- **No watermark, encryption or signature support** for PDFs.
- **No parallel rendering**; the build time (a few seconds per document) does not justify the complexity.

## 6. Reference usage

The author's production content does **not** live in this repo, but in a private knowledge vault. That vault only holds `config.yaml` + `content/de.yaml` + `content/en.yaml` and invokes `ergograph build` in that folder.
