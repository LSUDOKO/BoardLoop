"""Test setup: import the repo root as the ``boardloop`` package, exactly as Hermes does.

The repository root *is* the plugin (it holds ``plugin.yaml`` and ``__init__.py``), but the
folder name is not a valid package name, so we load it under its real name here.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FAKES = Path(__file__).resolve().parent / "fakes"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = ROOT / "examples"

if "boardloop" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "boardloop", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["boardloop"] = module
    spec.loader.exec_module(module)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("BOARDLOOP_REAL") == "1":
        return
    skip = pytest.mark.skip(reason="real-tool test; set BOARDLOOP_REAL=1")
    for item in items:
        if "real" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _pass_fake_switches(monkeypatch):
    """The fake CLIs read FAKE_* switches from their environment; let those through the
    child-process allow-list in tests only."""
    from boardloop import procs
    monkeypatch.setattr(procs, "PASS_PREFIXES", (*procs.PASS_PREFIXES, "FAKE_"))
