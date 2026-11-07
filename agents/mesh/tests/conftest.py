import os
import pathlib
import shutil
import sys

import pytest

os.environ.setdefault("SEANCE_PORT_BASE", "8880")  # tests use 8881-8884, never the production 8781-8784
ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
DATA = pathlib.Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    """Tests never read .env: no keys, no real seeds, no network."""
    from agents.mesh import base
    monkeypatch.setattr(base, "load_env", lambda: None)
    for k in ("SEANCE_MAILBOX", "SEANCE_FAKE_LLM", "SEANCE_FAKE_BENCH", "ASI1_API_KEY", "AGENTVERSE_API_KEY",
              "MCCLUSKY_SEED", "HOOT_SEED", "BAILIFF_SEED"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """A runs/ dir holding app1's dig output and the court tests' drifted revival, with both fakes on."""
    r = tmp_path / "runs"
    shutil.copytree(DATA / "app1", r / "app1")  # not data/runs/: the repo .gitignore drops every runs/ folder
    (r / "app1" / "revival").mkdir()
    shutil.copy(ROOT / "court" / "tests" / "revival_app1" / "index.html", r / "app1" / "revival")
    monkeypatch.setenv("SEANCE_FAKE_LLM", "1")
    monkeypatch.setenv("SEANCE_FAKE_BENCH", "1")
    return r
