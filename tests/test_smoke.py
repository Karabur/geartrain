"""Smoke tests — package imports and CLI entrypoint."""

import subprocess
import sys

import pytest


def test_package_imports():
    """All top-level modules should import without error."""
    import geartrain
    import geartrain.agents
    import geartrain.engine
    import geartrain.memory
    import geartrain.work
    import geartrain.workflows


def test_cli_help():
    """geartrain --help should exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, "-m", "geartrain.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "geartrain" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_cli_no_args_shows_help():
    """Running geartrain with no args should print help and exit non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "geartrain.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
