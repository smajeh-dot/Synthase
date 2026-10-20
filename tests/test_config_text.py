"""The words /config shows, read from an invented config."""

import pytest

from synthase.config import load_config
from synthase.config_text import (
    UNVERIFIED,
    VERIFIED,
    config_entries,
    config_row,
    count_line,
    entry_key,
    entry_rows,
    group_entries,
    read_settings,
    settings_heading,
)


def test_rows_show_each_value_without_its_unit(invented_config):
    config = load_config(invented_config)
    assert [config_row(entry) for entry in config_entries(config)] == [
        ("test.alpha", "2.5", "mg", VERIFIED, "Invented Handbook, p. 1"),
        ("test.beta", "1–3", "K", VERIFIED, "Invented Journal 1, 2"),
        ("test.gamma", "≤1 low, >1 high", "-", UNVERIFIED, "UNVERIFIED invented"),
        ("test.delta", "mL", "-", UNVERIFIED, "UNVERIFIED invented"),
    ]
    assert settings_heading(config) == f"Settings in {invented_config / 'config.toml'}"


def counted(folder):
    return count_line(config_entries(load_config(folder)))


def test_the_count_line_says_how_many_are_left(invented_config):
    assert counted(invented_config) == "2 of 4 values are still unverified."
    path = invented_config / "config.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("false", "true", 1), encoding="utf-8")
    assert counted(invented_config) == "1 of 4 values is still unverified."
    path.write_text(text.replace("false", "true"), encoding="utf-8")
    assert counted(invented_config) == "All 4 values are verified."


def test_a_group_is_the_entries_under_its_name(invented_config):
    config = load_config(invented_config)
    assert [entry.key for entry in group_entries(config, "test")] == [
        "test.alpha",
        "test.beta",
        "test.gamma",
        "test.delta",
    ]
    # Only whole names before the dot count, so "tes" is not a group.
    assert group_entries(config, "tes") == []
    assert group_entries(config, "test.alpha") == []
    assert settings_heading(config, "test") == (
        f"test settings in {invented_config / 'config.toml'}"
    )


def test_one_value_in_full(invented_config):
    entry = load_config(invented_config).get("test.gamma")
    assert entry_rows(entry) == [
        ("Name", "gamma bands"),
        ("Value", "≤1 low, >1 high"),
        ("Unit", "-"),
        ("Source", "UNVERIFIED invented"),
        ("Verified", "? no"),
    ]


@pytest.mark.parametrize(
    "typed", ["test.alpha", " TEST.Alpha ", "[test.alpha]", "[TEST.ALPHA]"]
)
def test_a_name_ignores_capitals_and_brackets(typed):
    assert entry_key(typed) == "test.alpha"


def test_settings_come_with_doctors_folder_lines(invented_config):
    settings = read_settings(init="/init")
    assert settings.problem is None
    assert [check.text for check in settings.folders] == [
        f"Compounds folder: {invented_config / 'tables'}"
    ]


def test_no_workspace_gives_doctors_check():
    settings = read_settings(init="/init")
    assert settings.config is None
    assert settings.problem.text == (
        'There is no workspace yet. Run "syn init" to create one.'
    )


def test_a_broken_config_gives_doctors_check(invented_config):
    path = invented_config / "config.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("verified = true", 'verified = "maybe"', 1), encoding="utf-8"
    )
    settings = read_settings(init="/init")
    assert settings.config is None
    assert settings.problem.text == (
        f"Your config file has a problem: {path}, entry [test.alpha]: 'verified' "
        "must be true or false. Fix that entry, or compare it with the template."
    )
