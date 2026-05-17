"""Tests for sentrix package init."""

import sentrix


def test_version() -> None:
    """Test package version is available."""
    assert sentrix.__version__ == "0.1.0"
