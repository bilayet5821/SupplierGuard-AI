from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TASK_DATA = (
    ROOT
    / "BIAI-AI-Engineer-Round2-Pack"
    / "sample-data"
    / "engineer"
    / "task1-procurement"
)
sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def task_data() -> Path:
    return TASK_DATA
