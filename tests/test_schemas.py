"""The shipped JSON Schemas must accept every bundled example.

The schemas exist for editor support (completion, typo detection). Validating
the examples against them keeps them from drifting away from what the loader
actually accepts, since the examples double as the test fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

jsonschema = pytest.importorskip("jsonschema")

ROOT = Path(__file__).parent.parent
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples"

CONFIGS = sorted(EXAMPLES.glob("*/config.yaml"))
CONTENTS = sorted(EXAMPLES.glob("*/content/*.yaml"))


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _validator(name: str):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def test_examples_exist():
    assert CONFIGS, "no example configs found"
    assert CONTENTS, "no example content files found"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.parent.name)
def test_config_matches_schema(path):
    errors = sorted(_validator("config.schema.json").iter_errors(_load(path)),
                    key=lambda e: list(e.absolute_path))
    assert not errors, "\n".join(
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors)


@pytest.mark.parametrize("path", CONTENTS,
                         ids=lambda p: f"{p.parent.parent.name}-{p.stem}")
def test_content_matches_schema(path):
    errors = sorted(_validator("content.schema.json").iter_errors(_load(path)),
                    key=lambda e: list(e.absolute_path))
    assert not errors, "\n".join(
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors)


def test_schema_rejects_a_missing_required_key():
    """A guard against a schema so loose that it accepts anything."""
    content = _load(CONTENTS[0])
    del content["skills"]
    errors = list(_validator("content.schema.json").iter_errors(content))
    assert errors, "schema accepted a content file without 'skills'"
