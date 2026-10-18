"""The text Synthase shows for the compound register.

The plain command line and the app both show these words. Nothing here
prints or asks anything.
"""

from pathlib import Path

from synthase.compounds import Batch, Compound, Spectrum, as_text, purity_warnings
from synthase.config import ConfigError, load_config


def aligned(rows: list[tuple[str | None, ...]]) -> list[str]:
    """``rows`` as lines of aligned columns, with - in each blank cell."""
    cells = [[cell or "-" for cell in row] for row in rows]
    widths = [
        max(len(line[column]) for line in cells) for column in range(len(cells[0]))
    ]
    return [
        "  ".join(
            cell.ljust(width) for cell, width in zip(line, widths, strict=True)
        ).rstrip()
        for line in cells
    ]


def detail_text(compound: Compound, field: str) -> str | None:
    if field == "risk_assessment" and compound.risk_assessment != "no":
        return f"done on {compound.risk_assessment}"
    if field == "risk_assessment":
        return "not done"
    return as_text(getattr(compound, field))


def purity_lines(compound: Compound, workspace: Path) -> list[str]:
    """The purity flag for ``compound``'s melting range, if it has one."""
    if compound.melting_point is None:
        return []
    try:
        return purity_warnings(compound, load_config(workspace))
    except ConfigError as error:
        return [f"The melting range can't be checked against the purity rule. {error}"]


def batch_cells(batch: Batch) -> tuple[str | None, ...]:
    return (str(batch.number), batch.made_on, batch.mass, batch.yield_text)


def spectrum_cells(spectrum: Spectrum, workspace: Path) -> tuple[str | None, ...]:
    found = "" if (workspace / spectrum.path).is_file() else "  (file not found)"
    return (
        spectrum.kind,
        str(Path(spectrum.path)),
        f"(added {spectrum.added[:10]}){found}",
    )


def spectrum_name(spectrum: Spectrum) -> str:
    """The kind and path of ``spectrum``, as the card shows them."""
    path = str(Path(spectrum.path))
    return path if spectrum.kind is None else f"{spectrum.kind} {path}"
