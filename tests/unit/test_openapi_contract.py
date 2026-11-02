import json
from pathlib import Path

from halo.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_committed_openapi_matches_the_application():
    committed = json.loads((ROOT / "contracts" / "openapi.json").read_text())
    current = app.openapi()
    assert set(current["paths"]) == set(committed["paths"])
