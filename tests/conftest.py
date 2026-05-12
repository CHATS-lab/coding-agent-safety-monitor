"""Shared pytest fixtures."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """Run with a temp directory as cwd so log paths don't pollute the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
