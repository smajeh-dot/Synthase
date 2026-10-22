"""The walk-through rules, without the app. Every question and answer is invented."""

from synthase.walkthrough import NEEDED, Question, Walk, Walkthrough, unquote


def walk(*questions, edit=False):
    return Walk(Walkthrough("project create", list(questions), print, edit=edit))


def no_digits(text):
    return "Digits aren't allowed." if any(c.isdigit() for c in text) else None


def test_answers_are_kept_by_name_and_spaces_trimmed():
    steps = walk(Question("title", "Title"), Question("notes", "Notes", optional=True))
    assert steps.answer("  Invented title ").shown == ["Invented title"]
    assert steps.answer("").shown == []
    assert steps.question is None
    assert steps.answers == {"title": "Invented title", "notes": None}


def test_an_empty_answer_to_a_needed_question_is_refused():
    steps = walk(Question("title", "Title"))
    assert steps.answer("   ").refused == NEEDED
    assert steps.number == 0


def test_a_check_refuses_with_its_reason():
    steps = walk(Question("title", "Title", check=no_digits))
    assert steps.answer("Run 2").refused == "Digits aren't allowed."
    assert steps.answer("Run two").refused is None
    assert steps.answers == {"title": "Run two"}


def test_an_edit_keeps_with_enter_and_clears_with_a_dash():
    steps = walk(
        Question("title", "Title", current="Old title"),
        Question("notes", "Notes", optional=True, current="Old notes"),
        Question("aim", "Aim", optional=True, current="Old aim"),
        edit=True,
    )
    assert steps.answer("").shown == ["Old title"]
    assert steps.answer("-").shown == []
    assert steps.answer("New aim").shown == ["New aim"]
    assert steps.answers == {"title": "Old title", "notes": None, "aim": "New aim"}


def test_a_needed_value_cant_be_cleared():
    steps = walk(Question("title", "Title", current="Old title"), edit=True)
    assert steps.answer("-").refused == NEEDED


def test_a_multi_line_question_ends_on_an_empty_line():
    steps = walk(Question("values", "Values", lines=True, check=no_digits))
    assert steps.answer("").refused == NEEDED
    first = steps.answer("mass")
    assert (first.shown, first.more) == (["mass"], False)
    assert steps.answer("volume 2").refused == "Digits aren't allowed."
    second = steps.answer("volume")
    assert (second.shown, second.more) == (["volume"], True)
    assert steps.answer("").shown is None
    assert steps.answers == {"values": ["mass", "volume"]}


def test_a_multi_line_edit_keeps_or_clears_on_its_first_line():
    current = ["mass", "volume"]
    kept = walk(Question("values", "V", lines=True, current=current), edit=True)
    assert kept.answer("").shown == current
    assert kept.answers == {"values": current}
    cleared = walk(
        Question("values", "V", lines=True, optional=True, current=current), edit=True
    )
    assert cleared.answer("-").shown == []
    assert cleared.answers == {"values": None}
    typed = walk(Question("values", "V", lines=True, current=current), edit=True)
    typed.answer("colour")
    assert not typed.keeping
    typed.answer("")
    assert typed.answers == {"values": ["colour"]}


def test_a_dragged_in_path_loses_its_quotes():
    assert unquote('  "C:\\Lab\\run 1.csv"  ') == "C:\\Lab\\run 1.csv"
    assert unquote("'C:\\Lab\\run 1.csv'") == "C:\\Lab\\run 1.csv"
    assert unquote('C:\\Lab\\"odd".csv') == 'C:\\Lab\\"odd".csv'
    assert unquote('"') == '"'
    steps = walk(Question("file", "File", path=True))
    steps.answer('"C:\\Lab\\run 1.csv"')
    assert steps.answers == {"file": "C:\\Lab\\run 1.csv"}
