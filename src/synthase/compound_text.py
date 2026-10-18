"""The text Synthase shows for the compound register.

The plain command line and the app both show these words. Nothing here
prints or asks anything.
"""

from dataclasses import dataclass
from pathlib import Path

from synthase.compounds import (
    DETAIL_GROUPS,
    FIELD_NAMES,
    Batch,
    Change,
    Compound,
    Spectrum,
    as_text,
    compound_batches,
    compound_spectra,
    missing_fields,
    parse_class,
    parse_status,
    purity_warnings,
)
from synthase.config import ConfigError, load_config
from synthase.numbers import sig_figs


@dataclass(frozen=True)
class Section:
    """One part of a compound's card.

    ``heading`` is None for the first fields. ``rows`` are (name, value)
    pairs, or a table's cells when ``table`` is set. ``warnings`` follow the
    rows.
    """

    heading: str | None
    rows: tuple[tuple[str | None, ...], ...]
    warnings: tuple[str, ...] = ()
    table: bool = False


@dataclass(frozen=True)
class Card:
    """Everything "show" says about a compound."""

    title: str
    sections: tuple[Section, ...]
    missing: tuple[str, ...]


def title(compound: Compound) -> str:
    archived = " (archived)" if compound.archived else ""
    return f"{compound.id}: {compound.label}{archived}"


def field_sections(compound: Compound, workspace: Path) -> list[Section]:
    """``compound``'s filled fields, then a section for each group of details.

    A group is left out when it has nothing to show.
    """
    molar_mass = (
        None
        if compound.molar_mass is None
        else f"{sig_figs(compound.molar_mass)} g/mol"
    )
    fields = tuple(
        (name, value)
        for name, value in (
            ("class", compound.compound_class),
            ("SMILES", compound.smiles),
            ("formula", compound.formula),
            ("molar mass", molar_mass),
            ("status", compound.status),
            ("notes", compound.notes),
        )
        if value is not None
    )
    sections = [Section(None, fields)]
    for group, names in DETAIL_GROUPS:
        rows = tuple(
            (FIELD_NAMES[field], detail_text(compound, field))
            for field in names
            if getattr(compound, field) is not None
        )
        warnings = ()
        if group == "Characterisation":
            warnings = tuple(purity_lines(compound, workspace))
        if rows or warnings:
            sections.append(Section(group, rows, warnings))
    return sections


def card(compound: Compound, workspace: Path) -> Card:
    """``compound``'s card, with its batches, spectra and what is missing."""
    batches = compound_batches(workspace, compound)
    spectra = compound_spectra(workspace, compound)
    sections = field_sections(compound, workspace)
    if batches:
        rows = tuple(batch_cells(batch) for batch in batches)
        warnings = tuple(
            f"! Batch {batch.number}: {batch.warning}"
            for batch in batches
            if batch.warning
        )
        sections.append(Section("Batches", rows, warnings, table=True))
    if spectra:
        rows = tuple(spectrum_cells(spectrum, workspace) for spectrum in spectra)
        sections.append(Section("Spectra", rows, table=True))
    missing = tuple(missing_fields(compound, batches, spectra))
    return Card(title(compound), tuple(sections), missing)


def section_lines(sections: list[Section] | tuple[Section, ...]) -> list[str]:
    """``sections`` as plain command-line lines, under their headings."""
    lines = []
    for section in sections:
        if section.heading is not None:
            lines.append(section.heading)
        if section.table:
            body = aligned(list(section.rows))
        else:
            width = 13 if section.heading is None else 20
            body = [f"{name:<{width}}{value}" for name, value in section.rows]
        lines += [f"  {line}" for line in [*body, *section.warnings]]
    return lines


def card_lines(shown: Card) -> list[str]:
    """``shown`` as the lines "syn compound show" prints."""
    lines = [shown.title, *section_lines(shown.sections), ""]
    if not shown.missing:
        return [*lines, "Nothing missing."]
    return [*lines, "Still missing:", *(f"  {item}" for item in shown.missing)]


def history_rows(changes: list[Change]) -> list[tuple[str, str, str, str]]:
    """Each change as (when, what, old value, new value), oldest first."""
    return [
        (
            (change.changed or "")[:16].replace("T", " "),
            change.name,
            *(
                "(blank)" if value is None else value
                for value in (change.old, change.new)
            ),
        )
        for change in changes
    ]


def history_lines(compound: Compound, changes: list[Change]) -> list[str]:
    """``compound``'s change log, as "syn compound history" prints it."""
    rows = history_rows(changes)
    width = max((len(name) for _, name, _, _ in rows), default=0)
    return [
        f"History of {compound.id}: {compound.label}",
        *(
            f"  {when}  {name:<{width}}  {old} -> {new}"
            for when, name, old, new in rows
        ),
    ]


def list_summary(
    shown: list[Compound],
    everything: list[Compound],
    status: str | None = None,
    compound_class: str | None = None,
    archived: bool = False,
) -> str:
    """The line under the compound list: the count, filters and hidden ones.

    ``everything`` is the whole register, archived compounds included, and
    must not be empty. When nothing is shown, the line says why instead.
    """
    filters = ", ".join(
        f"{name}: {value}"
        for name, value in (
            ("status", None if status is None else parse_status(status)),
            ("class", parse_class(compound_class or "")),
        )
        if value is not None
    )
    hidden = 0 if archived else sum(compound.archived for compound in everything)
    if not shown:
        if filters:
            return f"No compounds match ({filters})."
        return "Every compound is archived. Add --all to see them."
    total = len(everything) - hidden
    count = f"{total} compound{'' if total == 1 else 's'}"
    if filters:
        count = f"{len(shown)} of {count}"
    if hidden:
        them = "it" if hidden == 1 else "them"
        filters = "; ".join(
            part
            for part in (filters, f"{hidden} archived, hidden; add --all to see {them}")
            if part
        )
    return f"{count} ({filters})." if filters else f"{count}."


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
