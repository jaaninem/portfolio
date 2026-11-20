"""Shared fixtures for the pipeline and content tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "assets/scripts/script.py"


@pytest.fixture(scope="session")
def pipeline():
    """The photo pipeline script, imported by path since it is not a package."""
    spec = importlib.util.spec_from_file_location("photo_pipeline", PIPELINE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"Cannot import {PIPELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
