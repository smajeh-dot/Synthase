import pytest

from synthase import config, workspace
from synthase.workspace import FOLDERS, remember


@pytest.fixture(autouse=True)
def private_settings(tmp_path, monkeypatch):
    """Keep every test away from the real AppData and Documents folders."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(workspace, "documents_folder", lambda: tmp_path / "Documents")


@pytest.fixture
def invented_details():
    """Every characterisation, handling and safety field, with invented values."""
    return {
        "melting_point": "455-457",
        "rf": "0.45",
        "rf_solvent": "invented solvent 3:1",
        "appearance": "invented yellow powder",
        "coloured": "yes",
        "solubility": "invented: soluble in DMSO",
        "dmso_stock": "10 mg/mL",
        "storage": "invented: fridge",
        "risk_assessment": "2020-01-31",
        "hazards": "invented hazard note",
    }


# Invented values only: none of these is a real lab value.
INVENTED_CONFIG = """\
# An invented config for tests.

[test.alpha]
name = "alpha limit"
value = 2.5
unit = "mg"
source = "Invented Handbook, p. 1"
verified = true

[test.beta]
name = "beta range"
value = [1, 3]
unit = "K"
source = "Invented Journal 1, 2"
verified = true

[test.gamma]
name = "gamma bands"
value = [{ max = 1.0, label = "low" }, { label = "high" }]
unit = ""
source = "UNVERIFIED invented"
verified = false

[test.delta]
name = "delta unit"
value = "mL"
unit = ""
source = "UNVERIFIED invented"
verified = false

[folders]
compounds = 'tables'
"""


@pytest.fixture
def invented_config(tmp_path, monkeypatch):
    """A workspace whose config, and template, hold four invented values.

    Two are verified and two aren't, and the compounds folder is set.
    """
    template = tmp_path / "template.toml"
    template.write_text(INVENTED_CONFIG, encoding="utf-8")
    monkeypatch.setattr(config, "TEMPLATE", template)
    folder = tmp_path / "Synthase-data"
    folder.mkdir()
    for name in [*FOLDERS, "tables"]:
        (folder / name).mkdir()
    (folder / "config.toml").write_text(INVENTED_CONFIG, encoding="utf-8")
    remember(folder)
    return folder
