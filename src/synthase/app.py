"""The `synthase` command.

The old app was retired (decision 0020). Until the new full-screen app is built
(#92), the command only says so.
"""

from synthase import __version__

REBUILDING = (
    f"Synthase {__version__} is being rebuilt. "
    "The new app arrives with the Ledger: see ROADMAP.md."
)


def main() -> int:
    print(REBUILDING)
    return 0
