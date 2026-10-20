"""Editing the workspace config.toml, on an invented config in a temporary folder."""

import pytest

from synthase import config_edit
from synthase.config import ConfigError, load_config
from synthase.config_edit import (
    plan_folder,
    plan_set,
    plan_source,
    plan_verify,
    save_edit,
)


def config_text(folder):
    """The config's text, with \r\n read as \n so Windows CI sees the same."""
    return (folder / "config.toml").read_text(encoding="utf-8")


def untouched(before, after, changed):
    """Whether every line of ``before`` except those in ``changed`` is in ``after``.

    The lines also have to be in the same order.
    """
    kept = [line for line in before.splitlines() if line not in changed]
    lines = iter(after.splitlines())
    return all(line in lines for line in kept)


def test_set_a_number_asks_first_then_marks_it_unverified(invented_config):
    before = config_text(invented_config)
    edit = plan_set(invented_config, "test.alpha", "3")
    assert edit.question == (
        "Change alpha limit from 2.5 mg to 3 mg? It will be marked unverified "
        "until you check it again. Type yes to change it [no]"
    )
    assert edit.note == ""
    # Nothing is saved until the edit is.
    assert config_text(invented_config) == before
    save_edit(edit, back_up=False)
    assert edit.done == "Changed alpha limit to 3 mg. It is now unverified."
    entry = load_config(invented_config).get("test.alpha")
    assert (entry.value, entry.verified) == (3, False)
    assert entry.source == "Invented Handbook, p. 1"
    after = config_text(invented_config)
    assert untouched(before, after, {"value = 2.5", "verified = true"})
    assert "# An invented config for tests." in after


@pytest.mark.parametrize("typed", ["2 4", "2-4", "2 - 4", "2–4", " 2  4 "])
def test_set_a_range(invented_config, typed):
    save_edit(plan_set(invented_config, "test.beta", typed), back_up=False)
    entry = load_config(invented_config).get("test.beta")
    assert (entry.value, entry.verified) == ([2, 4], False)


@pytest.mark.parametrize(
    "typed",
    [
        "0.5 low, 2 middle, high",
        "≤0.5 low, ≤2 middle, >2 high",
        "<=0.5 low, <=2 middle, > 2 high",
    ],
)
def test_set_bands_as_config_shows_them(invented_config, typed):
    edit = plan_set(invented_config, "[TEST.Gamma]", typed)
    assert "to ≤0.5 low, ≤2 middle, >2 high?" in edit.question
    save_edit(edit, back_up=False)
    assert load_config(invented_config).get("test.gamma").value == [
        {"max": 0.5, "label": "low"},
        {"max": 2, "label": "middle"},
        {"label": "high"},
    ]
    assert '    { max = 0.5, label = "low" },\n' in config_text(invented_config)


def test_set_text_without_quotes(invented_config):
    save_edit(plan_set(invented_config, "test.delta", "µL"), back_up=False)
    assert load_config(invented_config).get("test.delta").value == "µL"


@pytest.mark.parametrize(
    ("name", "typed", "message"),
    [
        (
            "test.alpha",
            "lots",
            "[test.alpha] takes a number, e.g. config set test.alpha 2.5.",
        ),
        (
            "test.alpha",
            "nan",
            "[test.alpha] takes a number, e.g. config set test.alpha 2.5.",
        ),
        (
            "test.alpha",
            "2,5",
            "[test.alpha] takes a number, e.g. config set test.alpha 2.5.",
        ),
        (
            "test.beta",
            "2",
            "[test.beta] takes a range of two numbers, e.g. config set test.beta 1 3.",
        ),
        (
            "test.beta",
            "4 2",
            "That value can't be used for [test.beta]: a range must go from low "
            "to high.",
        ),
        (
            "test.gamma",
            "low, high",
            "[test.gamma] takes a list of bands, e.g. config set test.gamma 1 low, "
            "high.",
        ),
        (
            "test.gamma",
            "high",
            "[test.gamma] takes a list of bands, e.g. config set test.gamma 1 low, "
            "high.",
        ),
        (
            "test.gamma",
            "2 low, 1 middle, high",
            "That value can't be used for [test.gamma]: the band limits must "
            "increase from one band to the next.",
        ),
        (
            "test.gamma",
            "1 low, >2 high",
            "That value can't be used for [test.gamma]: the last band covers "
            "everything above the band before it, so it starts at >1.",
        ),
        (
            "test.zeta",
            "1",
            "The config has no entry called [test.zeta]. Check the spelling, or "
            "compare your config with the template.",
        ),
    ],
)
def test_a_refused_value_leaves_the_file_unchanged(
    invented_config, name, typed, message
):
    before = (invented_config / "config.toml").read_bytes()
    with pytest.raises(ConfigError) as error:
        plan_set(invented_config, name, typed)
    assert str(error.value) == message
    assert (invented_config / "config.toml").read_bytes() == before
    assert list(invented_config.glob("config.toml.*")) == []


def test_the_same_value_again_changes_nothing(invented_config):
    edit = plan_set(invented_config, "test.alpha", "2.50")
    assert edit.new_bytes is None
    assert edit.done == "alpha limit is already 2.5 mg."


def test_a_source_for_an_unverified_value_needs_no_question(invented_config):
    before = config_text(invented_config)
    edit = plan_source(invented_config, "test.delta", "Invented Tables, p. 9")
    assert edit.question == ""
    save_edit(edit, back_up=False)
    assert edit.done == "Changed the source of delta unit."
    assert edit.hint == (
        "Type config verify test.delta once you have checked the value against it."
    )
    entry = load_config(invented_config).get("test.delta")
    assert (entry.source, entry.verified) == ("Invented Tables, p. 9", False)
    assert untouched(
        before, config_text(invented_config), {'source = "UNVERIFIED invented"'}
    )


def test_a_source_for_a_verified_value_asks_and_unverifies_it(invented_config):
    edit = plan_source(invented_config, "test.alpha", 'Invented "Big" Book')
    assert edit.question == (
        'alpha limit is verified. Change its source to "Invented "Big" Book"? It '
        "will be marked unverified until you check it again. Type yes to change it "
        "[no]"
    )
    save_edit(edit, back_up=False)
    assert edit.done == "Changed the source of alpha limit. It is now unverified."
    entry = load_config(invented_config).get("test.alpha")
    assert (entry.source, entry.verified) == ('Invented "Big" Book', False)


def test_verify_asks_then_marks_it_verified(invented_config):
    save_edit(
        plan_source(invented_config, "test.delta", "Invented Tables"), back_up=False
    )
    edit = plan_verify(invented_config, "test.delta")
    assert edit.question == (
        'Mark delta unit (mL) as checked against "Invented Tables"? Type yes to '
        "mark it verified [no]"
    )
    save_edit(edit, back_up=False)
    assert edit.done == "Marked delta unit (mL) as verified."
    assert load_config(invented_config).get("test.delta").verified


def test_verify_refuses_a_placeholder_source(invented_config):
    with pytest.raises(ConfigError) as error:
        plan_verify(invented_config, "test.gamma")
    assert str(error.value) == (
        "Set its source first: config source test.gamma <reference>."
    )


def test_verify_an_already_verified_value_changes_nothing(invented_config):
    edit = plan_verify(invented_config, "test.alpha")
    assert edit.new_bytes is None
    assert edit.done == "alpha limit is already verified."


def test_set_a_folder_in_single_quotes_and_clear_it(invented_config):
    before = config_text(invented_config)
    edit = plan_folder(invented_config, "Compounds", r'"D:\Lab\Compound tables"')
    assert edit.question == ""
    save_edit(edit, back_up=False)
    assert edit.done == r"Tables for compounds will be saved in D:\Lab\Compound tables."
    after = config_text(invented_config)
    assert r"compounds = 'D:\Lab\Compound tables'" in after
    assert untouched(before, after, {"compounds = 'tables'"})
    assert load_config(invented_config).folder("compounds") == (
        r"D:\Lab\Compound tables"
    )

    edit = plan_folder(invented_config, "compounds", '""')
    save_edit(edit, back_up=False)
    assert edit.done == (
        "Cleared the compounds folder, so its tables are saved in the workspace's "
        "results folder."
    )
    assert load_config(invented_config).folder("compounds") == ""


def test_a_folder_with_an_apostrophe_uses_double_quotes(invented_config):
    save_edit(
        plan_folder(invented_config, "compounds", "D:/Sam's tables"), back_up=False
    )
    assert 'compounds = "D:/Sam\'s tables"' in config_text(invented_config)
    assert load_config(invented_config).folder("compounds") == "D:/Sam's tables"


def test_an_unknown_folder_setting_is_refused(invented_config):
    with pytest.raises(ConfigError) as error:
        plan_folder(invented_config, "plates", "D:/Lab")
    assert str(error.value) == (
        "There's no folder setting called 'plates'. The settings are: compounds."
    )


def test_a_folder_setting_is_added_when_the_file_has_no_folders(invented_config):
    path = invented_config / "config.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: text.index("[folders]")], encoding="utf-8")
    # The invented template's own setting is 'tables', so set another one.
    save_edit(plan_folder(invented_config, "compounds", "other"), back_up=False)
    assert load_config(invented_config).folder("compounds") == "other"
    assert config_text(invented_config).startswith(text[: text.index("[folders]")])


def test_an_entry_only_in_the_template_is_copied_first(invented_config):
    path = invented_config / "config.toml"
    text = path.read_text(encoding="utf-8")
    start = text.index("[test.delta]")
    without = text[:start] + text[text.index("[folders]") :]
    path.write_text(without, encoding="utf-8")
    edit = plan_set(invented_config, "test.delta", "µL")
    assert edit.note == (
        "[test.delta] isn't in config.toml yet, so it will be copied from the template."
    )
    # Answering no keeps the file as it was.
    assert path.read_text(encoding="utf-8") == without
    save_edit(edit, back_up=False)
    after = path.read_text(encoding="utf-8")
    assert after.startswith(without)
    assert '[test.delta]\nname = "delta unit"\nvalue = "µL"\n' in after
    entry = load_config(invented_config).get("test.delta")
    assert (entry.value, entry.source) == ("µL", "UNVERIFIED invented")


def test_windows_line_endings_and_same_line_comments_are_kept(invented_config):
    path = invented_config / "config.toml"
    text = path.read_text(encoding="utf-8").replace(
        "value = 2.5", "value = 2.5  # invented note"
    )
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    save_edit(plan_set(invented_config, "test.alpha", "3"), back_up=False)
    save_edit(
        plan_set(invented_config, "test.gamma", "1 low, 2 mid, high"), back_up=False
    )
    after = path.read_bytes().decode("utf-8")
    assert after.count("\n") == after.count("\r\n")
    assert "value = 3  # invented note\r\n" in after


def test_save_backs_up_the_old_file_when_asked(invented_config):
    path = invented_config / "config.toml"
    before = path.read_bytes()
    edit = plan_set(invented_config, "test.alpha", "3")
    backup = save_edit(edit, back_up=True)
    assert backup.name.startswith("config.toml.bak-")
    assert backup.read_bytes() == before
    assert (
        save_edit(plan_set(invented_config, "test.alpha", "4"), back_up=False) is None
    )
    assert list(invented_config.glob("config.toml.bak-*")) == [backup]


def test_save_refuses_when_the_file_changed_after_the_question(invented_config):
    path = invented_config / "config.toml"
    edit = plan_set(invented_config, "test.alpha", "3")
    path.write_text(config_text(invented_config) + "\n# saved in Notepad\n", "utf-8")
    changed = path.read_bytes()
    with pytest.raises(ConfigError) as error:
        save_edit(edit, back_up=True)
    assert str(error.value) == (
        "config.toml changed while you were answering, so nothing was saved. "
        "Type the command again."
    )
    assert path.read_bytes() == changed
    assert list(invented_config.glob("config.toml.*")) == []


def test_a_failed_save_leaves_the_old_file_whole(invented_config, monkeypatch):
    path = invented_config / "config.toml"
    before = path.read_bytes()

    def refuse(source, target):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(config_edit.os, "replace", refuse)
    with pytest.raises(ConfigError) as error:
        save_edit(plan_set(invented_config, "test.alpha", "3"), back_up=False)
    assert str(error.value) == (
        f"Couldn't save {path}: Access is denied. Nothing was changed. If it is "
        "open in another program, close it and try again."
    )
    assert path.read_bytes() == before
    assert sorted(p.name for p in invented_config.glob("config.toml*")) == [
        "config.toml"
    ]


def test_the_template_is_never_edited(tmp_path):
    from synthase.config import read_template

    template = read_template()
    folder = tmp_path / "empty"
    folder.mkdir()
    with pytest.raises(ConfigError):
        plan_set(folder, "mic.growth_threshold", "0.2")
    assert read_template() == template
