"""The questions Synthase asks for the compound register.

The plain command line and the app both ask these questions, in this order
and with these words. Nothing here prints or asks anything: each guided flow
is a list of questions, and whoever asks them checks each typed answer with
``Question.answer``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from synthase.compound_text import aligned, spectrum_cells
from synthase.compounds import (
    CLASSES,
    CLEAR,
    DEFAULT_STATUS,
    DETAIL_GROUPS,
    DETAIL_PARSERS,
    DETAILS,
    SPECTRUM_KINDS,
    STATUSES,
    Batch,
    Change,
    Compound,
    CompoundError,
    as_text,
    check_label,
    check_rf,
    compound_spectra,
    parse_batch_date,
    parse_batch_value,
    parse_class,
    parse_field,
    parse_mass,
    parse_spectrum_kind,
    parse_status,
    parse_yield,
    read_smiles,
    spectra_path,
)

# The answers given so far, by question key.
type Answers = dict[str, object]

# The fields add and edit take, as Compound attributes and option names.
FIELDS = ("label", "compound_class", "smiles", "status", "notes", *DETAILS)

# What each group of details covers, and the question for each field.
GROUP_CONTENTS = {
    "Characterisation": "melting point, Rf",
    "Handling": "appearance, colour, solubility, DMSO stock, storage",
    "Safety": "risk assessment, hazards",
}
QUESTIONS = {
    "melting_point": "Melting range in K (e.g. 455-457)",
    "rf": "Rf (0 to 1)",
    "rf_solvent": "Rf solvent system (e.g. hexane:ethyl acetate 3:1)",
    "appearance": "Appearance and colour",
    "coloured": "Coloured in solution, so it needs a compound-only blank? (yes/no)",
    "solubility": "Solubility",
    "dmso_stock": "DMSO stock concentration (mg/mL, µg/mL or mM)",
    "storage": "Storage conditions",
    "risk_assessment": "Risk assessment (the date it was done, e.g. 2026-10-18, or no)",
    "hazards": "Hazard notes",
}

NEEDS_MASS_OR_YIELD = "A batch needs its mass made, its yield or both."


def always(answers: Answers) -> bool:
    return True


@dataclass(frozen=True)
class Question:
    """One question in a guided flow.

    ``key`` names the answer. ``current`` is the value Enter keeps, shown in
    brackets after ``text``. ``check`` turns the typed text, given the answers
    so far, into the answer, or raises CompoundError saying what is wrong.
    ``skippable`` says whether Enter is accepted. A ``yes_no`` question is a
    [y/N] question: only yes or y counts as yes. ``asked`` says, from the
    earlier answers, whether the question is asked at all. ``kept`` is the
    line shown when a [y/N] question is answered anything but yes.
    """

    key: str
    text: str
    check: Callable[[str, Answers], object]
    current: str | None = None
    skippable: bool = True
    yes_no: bool = False
    asked: Callable[[Answers], bool] = always
    kept: str | None = None

    @property
    def prompt(self) -> str:
        """The question exactly as shown, ready for the answer to follow."""
        if self.yes_no:
            return f"{self.text} [y/N] "
        shown = "" if self.current is None else f" [{self.current}]"
        return f"{self.text}{shown}: "

    def answer(self, text: str, answers: Answers) -> object:
        """The answer ``text`` gives, or CompoundError saying what is wrong."""
        return self.check(text, answers)


@dataclass(frozen=True)
class Flow:
    """A guided flow: the lines shown first, then the questions in order."""

    opening: tuple[str, ...]
    questions: tuple[Question, ...]

    def next_question(self, answers: Answers) -> Question | None:
        """The next question to ask, or None once every one is answered."""
        for question in self.questions:
            if question.key not in answers and question.asked(answers):
                return question
        return None


def is_yes(text: str) -> bool:
    """Whether ``text`` answers a [y/N] question yes: only "yes" or "y" does."""
    return text.strip().lower() in ("y", "yes")


def text_only(check: Callable[[str], object]) -> Callable[[str, Answers], object]:
    """A check that needs only the typed text, not the earlier answers."""
    return lambda text, answers: check(text)


def after(answer: str | None, current: object) -> object:
    """What a field holds after ``answer``: kept, cleared or replaced."""
    if answer is None:
        return current
    return None if answer.strip() == CLEAR else answer


def check_smiles(text: str) -> str | None:
    smiles = text.strip()
    if smiles:
        read_smiles(smiles)
    return smiles or None


def compound_answers(answers: Answers) -> dict[str, object]:
    """The answers add_compound and edit_compound take, by field."""
    return {key: value for key, value in answers.items() if key not in GROUP_CONTENTS}


def add_flow(workspace: Path) -> Flow:
    """The questions for a new compound. Only the label can't be skipped."""
    return Flow(
        ("New compound. Press Enter to skip any question except the label.",),
        (
            Question(
                "label",
                "Label",
                lambda text, answers: check_label(workspace, text),
                skippable=False,
            ),
            Question(
                "compound_class",
                f"Class ({', '.join(CLASSES)})",
                text_only(parse_class),
            ),
            Question("smiles", "SMILES", text_only(check_smiles)),
            Question(
                "status", "Status", text_only(parse_status), current=DEFAULT_STATUS
            ),
            Question("notes", "Notes", lambda text, answers: text),
            *detail_questions(workspace, None),
        ),
    )


def edit_flow(workspace: Path, compound: Compound) -> Flow:
    """The questions for editing ``compound``, each showing its current value.

    Each answer is None to keep the value, or the text typed.
    """
    return Flow(
        (
            f"Editing {compound.id}: {compound.label}. "
            "Press Enter to keep a value, or type - to clear it.",
        ),
        (
            edit_question(workspace, compound, "label", "Label", compound.label),
            edit_question(
                workspace,
                compound,
                "class",
                f"Class ({', '.join(CLASSES)})",
                compound.compound_class,
            ),
            edit_question(workspace, compound, "smiles", "SMILES", compound.smiles),
            edit_question(
                workspace,
                compound,
                "status",
                f"Status ({', '.join(STATUSES)})",
                compound.status,
            ),
            edit_question(workspace, compound, "notes", "Notes", compound.notes),
            *detail_questions(workspace, compound),
        ),
    )


def edit_question(
    workspace: Path, compound: Compound, field: str, text: str, current: str | None
) -> Question:
    """A question about one of ``compound``'s first five fields."""

    def check(typed: str, answers: Answers) -> str | None:
        if not typed.strip():
            return None
        parse_field(workspace, compound.number, field, typed)
        return typed

    key = "compound_class" if field == "class" else field
    return Question(key, text, check, current=current)


def detail_questions(workspace: Path, compound: Compound | None) -> list[Question]:
    """Each group question, then the questions it opens.

    ``compound`` is the one being edited, or None for a new one.
    """
    verb = "Add" if compound is None else "Edit"
    questions = []
    for group, fields in DETAIL_GROUPS:
        questions.append(
            Question(
                group,
                f"{verb} {group.lower()} details ({GROUP_CONTENTS[group]})?",
                text_only(is_yes),
                yes_no=True,
            )
        )
        questions.extend(
            detail_question(workspace, compound, group, field) for field in fields
        )
    return questions


def detail_question(
    workspace: Path, compound: Compound | None, group: str, field: str
) -> Question:
    """The question for one detail, asked only after a yes to its group."""
    current = None if compound is None else getattr(compound, field)

    def check(text: str, answers: Answers) -> str | None:
        if not text.strip():
            answer = None
        elif compound is None:
            DETAIL_PARSERS[field](text)
            answer = text
        else:
            parse_field(workspace, compound.number, field, text)
            answer = text
        if field == "rf_solvent":
            old_rf = None if compound is None else compound.rf
            check_rf(after(answers.get("rf"), old_rf), after(answer, current))
        return answer

    def asked(answers: Answers) -> bool:
        if not answers[group]:
            return False
        # A new compound is asked for the solvent system only if it has an Rf.
        return field != "rf_solvent" or compound is not None or bool(answers["rf"])

    return Question(field, QUESTIONS[field], check, as_text(current), asked=asked)


def batch_flow(compound: Compound) -> Flow:
    """The questions for a new batch of ``compound``: its date, mass and yield."""

    def check_mass(text: str, answers: Answers) -> float | None:
        return parse_mass(text) if text.strip() else None

    def check_yield(text: str, answers: Answers) -> float | None:
        if text.strip():
            return parse_yield(text)
        if answers["mass_g"] is None:
            raise CompoundError(NEEDS_MASS_OR_YIELD)
        return None

    return Flow(
        (
            f"New batch of {compound.id}: {compound.label}. Press Enter for today's "
            "date, or to skip the mass or the yield.",
        ),
        (
            Question(
                "made_on", "Date made (e.g. 2026-10-18)", text_only(parse_batch_date)
            ),
            Question("mass_g", "Mass made (e.g. 152 mg)", check_mass),
            Question("yield_percent", "Yield in % (e.g. 64.2)", check_yield),
        ),
    )


def edit_batch_flow(compound: Compound, batch: Batch) -> Flow:
    """The questions for correcting ``batch``, each showing its current value.

    Each answer, keyed by edit_batch option, is None to keep the value, or the
    text typed.
    """
    return Flow(
        (
            f"Editing batch {batch.number} of {compound.id}: {compound.label}. "
            "Press Enter to keep a value, or type - to clear the mass or yield.",
        ),
        (
            batch_question(batch, "made_on", "date", "Date made", batch.made_on),
            batch_question(batch, "mass", "mass", "Mass made", batch.mass),
            batch_question(
                batch, "yield_percent", "yield", "Yield in %", batch.yield_text
            ),
        ),
    )


def batch_question(
    batch: Batch, option: str, part: str, text: str, current: str | None
) -> Question:
    """A question about one of ``batch``'s values."""

    def check(typed: str, answers: Answers) -> str | None:
        answer = typed if typed.strip() else None
        if answer is not None:
            parse_batch_value(part, answer)
        if part == "yield" and (
            after(answers["mass"], batch.mass_g) is None
            and after(answer, batch.yield_percent) is None
        ):
            raise CompoundError(NEEDS_MASS_OR_YIELD)
        return answer

    return Question(option, text, check, current=current)


def spectrum_flow(workspace: Path, compound: Compound) -> Flow:
    """The questions for linking a spectra file to ``compound``: file and kind."""

    def check_file(text: str, answers: Answers) -> Path:
        if not text.strip():
            raise CompoundError("Type the file's path, or drag the file in.")
        # A file dragged into PowerShell arrives in quotes.
        file = Path(text.strip().strip('"'))
        spectra_path(workspace, file)
        return file

    return Flow(
        (f"Link a spectra file to {compound.id}: {compound.label}.",),
        (
            Question("file", "File", check_file, skippable=False),
            Question(
                "kind",
                f"Kind ({', '.join(SPECTRUM_KINDS)})",
                text_only(parse_spectrum_kind),
            ),
        ),
    )


def unlink_flow(workspace: Path, compound: Compound) -> Flow:
    """The files linked to ``compound``, numbered, then which one to unlink.

    The answer is the file's path. Raises CompoundError if none is linked.
    """
    linked = compound_spectra(workspace, compound)
    if not linked:
        raise CompoundError(f"{compound.id} has no spectra linked.")
    rows = [
        (str(number), *spectrum_cells(spectrum, workspace))
        for number, spectrum in enumerate(linked, start=1)
    ]
    choices = "1" if len(linked) == 1 else f"1-{len(linked)}"

    def check(text: str, answers: Answers) -> str:
        if text.strip() not in [row[0] for row in rows]:
            raise CompoundError(f"Type the number of the file to unlink ({choices}).")
        return linked[int(text) - 1].path

    return Flow(
        (
            f"Spectra linked to {compound.id}: {compound.label}",
            *(f"  {line}" for line in aligned(rows)),
        ),
        (Question("file", f"Which one? ({choices})", check, skippable=False),),
    )


def archive_question(compound: Compound) -> Question:
    """The [y/N] question asked before archiving ``compound``."""
    return Question(
        "archive",
        f"Archive {compound.id} ({compound.label})? It stays in the register "
        'but is hidden from "syn compound list".',
        text_only(is_yes),
        yes_no=True,
        kept=f"Kept {compound.id} as it was.",
    )


def remove_batch_question(compound: Compound, batch: Batch) -> Question:
    """The [y/N] question asked before removing ``batch`` of ``compound``."""
    return Question(
        "remove",
        f"Remove batch {batch.number} of {compound.id} ({batch.details})? "
        "It is hidden from the card but kept in the history, and the other "
        "batches keep their numbers.",
        text_only(is_yes),
        yes_no=True,
        kept=f"Kept batch {batch.number} of {compound.id} as it was.",
    )


def change_name(change: Change) -> str:
    """How a confirmation names the value ``change`` changes."""
    # A batch's value, logged as "batch 1 mass", is asked about as "batch 1's mass".
    batch, _, part = change.name.rpartition(" ")
    return f"{batch}'s {part}" if batch.startswith("batch ") else f"the {change.name}"


def change_question(change: Change) -> str:
    """The [y/N] question asked before changing or clearing a set value."""
    return confirm_question("change", change).prompt


def confirm_question(key: str, change: Change) -> Question:
    """``change_question`` as a question, with ``kept_message`` for a no."""
    name = change_name(change)
    if change.new is None:
        text = f'Clear {name} ("{change.old}")?'
    else:
        text = f'Change {name} from "{change.old}" to "{change.new}"?'
    return Question(
        key, text, text_only(is_yes), yes_no=True, kept=kept_message(change)
    )


def confirm_flow(changes: list[Change]) -> Flow:
    """A question for each change to a set value, keyed by its place in ``changes``.

    Filling a blank value needs no question.
    """
    return Flow(
        (),
        tuple(
            confirm_question(str(number), change)
            for number, change in enumerate(changes)
            if change.old is not None
        ),
    )


def confirmed(changes: list[Change], answers: Answers) -> set[Change]:
    """The changes confirm_flow's ``answers`` allow: every fill, and each yes."""
    return {
        change
        for number, change in enumerate(changes)
        if change.old is None or answers[str(number)]
    }


def kept_message(change: Change) -> str:
    """The line shown when the answer to change_question isn't yes."""
    return f'Kept {change_name(change)} as "{change.old}".'
