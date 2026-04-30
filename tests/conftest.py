"""Shared fixtures for the test suite."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary directory pre-populated with sample data."""
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path
