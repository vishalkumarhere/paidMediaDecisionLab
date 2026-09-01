import json
from pathlib import Path
import pytest
from luxe_lab.storage import ROOT

@pytest.fixture
def config():
    return json.loads((ROOT/'config/default.json').read_text())

@pytest.fixture
def financial():
    return json.loads((Path(__file__).parent/'fixtures/financial.json').read_text())

