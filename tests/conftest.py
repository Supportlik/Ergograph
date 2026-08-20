from pathlib import Path

import pytest

from ergograph.config import load_config, load_content

EXAMPLES = Path(__file__).parent.parent / "examples" / "minimal"


@pytest.fixture(scope="session")
def example_config():
    return load_config(EXAMPLES / "config.yaml")


@pytest.fixture(scope="session")
def example_content_de(example_config):
    return load_content(example_config.content["de"])
