import pytest

from synthase import workspace


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
