# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-09-24

### Added

- Photo in the header (R24). `photo:` in the config names a JPEG or PNG, the
  documents and languages that show it and optionally another file per
  document. The file is embedded byte for byte, in the PDF (Chrome passes the
  JPEG through) as in the DOCX, where it is an anchored picture with rounded
  corners top right. No scaling, no re-encoding (D30).
- The one-pager (R25): a new document `onepager`, landscape A4, that has to fit
  on one page or the build fails. It reuses contact, facts, certificates and
  languages and references project items by `id`; its own block adds the
  summary, key figures, competency clusters and a timeline. PDF and Markdown
  only (D31).
- Markdown export (R26): `formats: [..., md]` writes every document as plain,
  copy-paste-ready Markdown, verified against the content strings like the
  DOCX.
- Variants in the mapping form (R27): options `tags`, `anonymous`, `documents`
  and `photo` per variant. `variants`/`except_variants` now filter entries of
  every list, and any value can be written as `{by_variant: …}` (D32).
- Anonymous variants (R27): no name, contact block, photo or links,
  `anonymous_name` in the header, `anonymous_replace` to generalize employers
  and systems, and a build that fails when any identity marker is left (D33).
- `output.flat_dir` (R28): every output also lands in one flat folder with
  variant and language in the file name, replacing earlier builds (D34);
  `output.flat_documents` limits which documents go there.
- `docs/tools/make_placeholder_photo.py` draws the placeholder portrait of the
  `software-architect` example, which now shows photo, one-pager, an anonymous
  variant and Markdown.

### Changed

- The default `documents` stay `cv, projects, skills, full`; `onepager` is
  opt-in. `doc_names.onepager` is only required when it is built.
- `filter_facts` is kept for compatibility and now delegates to
  `variants.resolve`, which also removes the `variants` keys from the entries.

## [1.1.0] - 2026-09-11

### Added

- DOCX export. `formats: [pdf, docx]` in the config (or `--format docx` on the
  command line) writes each document as an editable Word file next to the PDF,
  into `output.docx_dir` and with the same file-name convention (R23). The
  motivation is practical: agencies regularly ask for a CV "in Word format"
  before forwarding it to their client.
- The Word files are generated from the same content tree as the HTML, with the
  same section order, and every build verifies that: the text layer is extracted
  from the package and checked against the full set of content strings with the
  machinery that already guards ATS readability for PDFs. A missing string fails
  the build (D20).
- The Word files reproduce the `modern` theme rather than being plain
  documents: same palette, same type scale, the two-column CV grid, the blue
  rule under the header, hairlines under the section headings, right-aligned
  periods, pill-shaped skill tags, the accent bar beside each project and the
  level bars of the skills matrix (D21).
- The CV is no longer built from a table at all: the main column is flowing
  text indented past the sidebar, and the sidebar is an anchored text frame
  beside it. The reading view of Word for the web moves any table to a new
  page as soon as something precedes it, whatever its height, while the
  editing view renders the same file correctly; without a table both agree
  with the PDF (D23, D27).
- Line heights are set once, centrally: every paragraph states an exact
  height of 1.5 x its own font size, the way the theme does, instead of
  Word's multiple of the font's line height, which renders a quarter taller
  (D28).
- A position is never split across pages, a period never broken in half, and
  a skill pill never torn apart mid-label (D29).
- The core-competency pills match the theme's geometry: pill-height rows with
  the 4px gap between them, wrapped in the generator so the rows break where
  the PDF breaks them. Their corners stay square — a rounded corner needs a
  shape, a shape needs its own text box, and the sidebar is already one
  (D21).
- The level bars of the skills matrix are inline pictures, so they have the
  rounded ends, the blue gradient and the full grid width of the CSS bar
  instead of being approximated by shaded spaces (D25). The PNGs are written
  with the standard library, so the dependency set is unchanged.
- The skills matrix is typeset as paragraphs in a two-column section rather
  than as a table, which is what makes `break-inside: avoid` on a category
  work in Word for the web: categories are no longer torn in half and notes
  stay with their skill (D26).
- The Word files paginate like the PDF: same page count per document and the
  same break points. This required fixing three unit mismatches — page margins
  (the theme's 14/15 mm, not 20 mm), line height (CSS multiplies the font
  size, Word the font's line height) and the extra width Arial needs compared
  with the theme's Inter (D24). Verified page by page in Word for the web in
  both languages: CV 2 pages, project history 3, skills matrix 2, combined
  dossier 6, with the same break points as the PDF — in the reading view,
  which is the stricter of the two renderers and the one that matches a
  desktop Word (D27).
- `output.docx_font` to set the base font of the generated documents
  (default `Segoe UI`, the theme's own second choice, which is close to Inter
  in width and ships with every Word installation; the font is pinned on
  every run so simple readers cannot fall back to a serif, D22).

### Fixed

- `.entry .role` was set at 11 pt where the theme states 11.2 px, a third too
  large, which also pushed the period off the role's line for the longest
  job title.
- A `w:sectPr` without `w:type` defaults to `nextPage` in OOXML, not to
  "no break"; every section now states its type, which is what kept the
  standalone skills matrix from opening on a page of its own.
- A page break is a `w:pageBreakBefore` on the following paragraph rather
  than a paragraph of its own, which used to leave a blank line at the top
  of the new page.
- The paragraph that has to follow a table is hidden text, so it can no
  longer open an empty trailing page.

### Changed

- `ergograph build` gained `--format` (repeatable) to override the configured
  output formats for a single run.

### Notes

- No new dependency: the OOXML package is written with the standard library, so
  the runtime set stays at PyYAML + pypdf. `python-docx` would have pulled in
  `lxml`, a multi-megabyte binary wheel (D19).
- Existing configurations are unaffected. `formats` defaults to `[pdf]`, so a
  config that does not mention it builds exactly what it built before.

## [1.0.1] - 2026-08-20

### Added

- `docs/CONFIGURATION.md`: a field-by-field reference for `config.yaml` and the
  content files — type, required, default, and which region each key renders —
  introduced by an annotated screenshot of a rendered CV (R20).
- JSON Schemas for both file types under `schemas/`, for editor completion and
  typo detection, validated against every bundled example by the test suite (D18).
- A documented workflow for generating content files with an AI agent, including a
  prompt template and the manual review checklist (R22).

### Changed

- The example personas no longer overlap with the author's real dossier. The
  `software-architect` persona had been derived from it; certificates, role
  titles, capacity statements, project group names and skill notes were replaced
  after a field-wise comparison, down to zero matching values (R21).
- README: the content-file section now leads with the annotated picture and links
  to the reference instead of listing all keys in one sentence; all snippets use
  English values from the fictional example person.

## [1.0.0] - 2026-08-20

First public release on PyPI. The format of `config.yaml` and of the content files is
now covered by semantic versioning: breaking changes to it require a major release.

### Added

- Continuous integration on GitHub Actions: the test suite across Python 3.10–3.14,
  plus `validate` and `build --html-only` over every bundled example (R17).
- Security scanning: `pip-audit` against the locked dependency set, Trivy
  (vulnerabilities, secrets, misconfigurations), CodeQL, and dependency review on
  pull requests, all reporting into GitHub code scanning (R18).
- Automated releases via PyPI trusted publishing on `v*` tags, gated on the test
  suite and on the tag matching the built version (R19).
- Weekly Dependabot updates for dependencies and pinned action versions.
- PyPI classifiers and project URLs (repository, issues, changelog, specification).

### Changed

- **Page numbers and the ATS check are no longer optional.** They moved from
  PyMuPDF (an 18-23 MB binary wheel behind the extra `ergograph[pagenumbers]`) to
  pypdf (374 kB, pure Python), which is now a regular dependency: `pip install
  ergograph` delivers both. Verified during the switch — identical stamp position
  to 0.1 pt with 0 differing pixels at 150 dpi, and 0 missing strings out of 1,639
  across the 18 example PDFs with either library (D9). The extra `pagenumbers` is
  kept as an empty alias, so the old install command still works.
- The version is stamped only in `src/ergograph/__init__.py` and read from there by
  the build backend, so `--version` and the package metadata can no longer drift
  apart (D15). The stamps had in fact drifted: 0.4.0 and 0.5.0 shipped with a
  `pyproject.toml` still reading 0.3.4.
- `uv.lock` is committed, which makes CI reproducible and lets Trivy and pip-audit
  scan the exact dependency set users install (D16).
- The sdist no longer carries the rendered example PDFs (4.5 MB → 52 kB); the
  example YAML files stay in, as they double as the test fixtures.

## [0.5.0] - 2026-08-20

### Added

- Six example personas (`examples/<persona>/`) instead of the single example.
- Empty sections are hidden instead of rendering an empty heading.

### Changed

- In the combined dossier, every part starts on its own page again (D14a).

## [0.4.0] - 2026-08-20

### Added

- Optional `period` and `org` metadata for project items; structured bullets.

## [0.3.4] - 2026-08-18

### Fixed

- The ATS check tolerates line wraps after en dashes.

## [0.3.3] - 2026-08-18

### Changed

- Publication summaries render as their own paragraph.

## [0.3.2] - 2026-08-18

### Added

- Optional publication summaries.

### Changed

- The dossier parts are placed on their own pages again.

## [0.3.1] - 2026-08-18

### Changed

- Publication proof links are styled like certificate links.

## [0.3.0] - 2026-08-18

### Changed

- Layout refinements from an external design review (D14): project-history
  typography matching the CV, a two-column skills matrix, and page-break rules.

### Fixed

- The ATS check handles `<br>` correctly.

## [0.2.0] - 2026-08-17

### Added

- ATS readability check (R15/D13), PDF metadata, and committed example output.

## [0.1.0] - 2026-08-17

### Added

- Initial release: YAML-driven CV and dossier generator with HTML rendering,
  the `modern` theme, PDF export via Chrome headless, and optional page numbers.

[1.2.0]: https://github.com/Supportlik/Ergograph/releases/tag/v1.2.0
[1.1.0]: https://github.com/Supportlik/Ergograph/releases/tag/v1.1.0
[1.0.1]: https://github.com/Supportlik/Ergograph/releases/tag/v1.0.1
[1.0.0]: https://github.com/Supportlik/Ergograph/releases/tag/v1.0.0
