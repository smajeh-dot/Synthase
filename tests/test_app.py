from synthase import __version__
from synthase.app import main


def test_synthase_says_it_is_being_rebuilt(capsys):
    assert main() == 0
    assert capsys.readouterr().out == (
        f"Synthase {__version__} is being rebuilt. "
        "The new app arrives with the Ledger: see ROADMAP.md.\n"
    )
