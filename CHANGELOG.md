# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[1.0.0]: https://github.com/Supportlik/Ergograph/releases/tag/v1.0.0
