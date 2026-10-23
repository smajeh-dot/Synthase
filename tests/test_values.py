import pytest

from synthase.commands import CommandError, parse
from synthase.values import UNITS, Entry, EntryError, check_unit, read_entry

# The owner's unit list, word for word from decision 0032, so a change to
# `values.UNITS` has to be a change here too.
OWNERS_UNITS = [
    "g", "kg", "mg", "ug",
    "L", "mL", "uL", "cm^3", "dm^3",
    "mol", "mmol", "umol",
    "mol/dm^3", "mol dm^-3", "M", "mM",
    "g/mol", "g mol^-1", "g/cm^3", "g cm^-3", "g/dm^3", "g dm^-3", "%",
    "K", "degC",
    "s", "min", "h",
    "J", "kJ", "J/mol", "kJ/mol", "J mol^-1", "kJ mol^-1",
    "Pa", "kPa", "bar", "atm",
    "Hz",
    "s^-1", "min^-1", "dm^3/mol/s",
    "none",
]  # fmt: skip


def entry(line: str) -> Entry:
    return read_entry(parse(line).args)


def refused(line: str) -> str:
    with pytest.raises(EntryError) as raised:
        entry(line)
    return str(raised.value)


def test_the_issue_example_keeps_every_part_exactly():
    assert entry("value add m_crude 2.2110 g +/- 0.001 # Balance B2") == Entry(
        "m_crude", "2.2110", "g", "0.001", "Balance B2"
    )


def test_an_entry_without_uncertainty_or_note_has_none():
    assert entry("value edit m_crude 2.215 g") == Entry(
        "m_crude", "2.215", "g", None, None
    )


@pytest.mark.parametrize(
    "number",
    ["2.1", "-0.5", "+3", ".5", "5.", "1.0e-5", "1.0E5", "2.100", "0", "007"],
)
def test_a_number_is_kept_as_typed(number):
    assert entry(f"value add m {number} g").value == number


@pytest.mark.parametrize(
    ("typed", "reading"),
    [("2.1O", "2.10"), ("1,5", "1.5"), ("l.5", "1.5")],
)
def test_a_near_number_is_refused_with_the_closest_reading(typed, reading):
    assert refused(f"value add m {typed} g") == (
        f"'{typed}' isn't a number. Did you mean: {reading}?"
    )


@pytest.mark.parametrize("typed", ["1/2", "abc", "1.2.3", "e5", "1e", "-", "."])
def test_other_numbers_are_refused_without_a_suggestion(typed):
    assert refused(f"value add m {typed} g") == f"'{typed}' isn't a number."


def test_the_uncertainty_follows_the_same_number_rule():
    assert entry("value add m 2.1 g +/- 1e-3").uncertainty == "1e-3"
    assert refused("value add m 2.1 g +/- 0,001") == (
        "'0,001' isn't a number. Did you mean: 0.001?"
    )


@pytest.mark.parametrize("name", ["m_crude", "m_crude(2)", "M_crude", "x" * 64, "µ"])
def test_a_name_is_kept_as_typed(name):
    assert entry(f"value add {name} 1 g").name == name


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("x" * 65, "A value name can be at most 64 characters."),
        ("#x", "A value name can't start with '#'."),
        ("+/-", "A value name can't be '+/-'."),
        ("rxn_x", "Names starting with rxn_ are kept for reaction records."),
        ("rxn_", "Names starting with rxn_ are kept for reaction records."),
    ],
)
def test_a_bad_name_is_refused(name, message):
    # `#x` and `+/-` can't come through the command table; a CSV row can.
    with pytest.raises(EntryError) as raised:
        read_entry({"name": name, "value": "1", "unit": "g"})
    assert str(raised.value) == message


def test_the_issue_example_rxn_x_is_refused():
    assert refused("value add rxn_x 1 g") == (
        "Names starting with rxn_ are kept for reaction records."
    )


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "A value name can't be empty."),
        ("m crude", "A value name can't contain spaces."),
    ],
)
def test_an_empty_or_spaced_name_is_refused_from_a_csv_row(name, message):
    with pytest.raises(EntryError) as raised:
        read_entry({"name": name, "value": "1", "unit": "g"})
    assert str(raised.value) == message


def test_a_name_is_case_sensitive():
    assert entry("value add Rxn_x 1 g").name == "Rxn_x"


def test_the_unit_list_is_the_owners_list():
    assert set(UNITS) == set(OWNERS_UNITS)
    assert len(UNITS) == len(set(UNITS)) == 43


@pytest.mark.parametrize("unit", OWNERS_UNITS)
def test_every_listed_unit_is_kept_as_typed(unit):
    assert entry(f"value add m 1 {unit}").unit == unit
    assert entry(f"value add m 1 {unit} +/- 0.1 # n").unit == unit


def test_a_unit_with_spaces_is_read_up_to_the_uncertainty():
    call = parse("value add c 0.100 mol dm^-3 +/- 0.001 # Burette")
    assert call.args["unit"] == "mol dm^-3"
    assert call.args["uncertainty"] == "0.001"
    assert call.args["note"] == "Burette"


def test_a_unit_typo_suggests_the_two_closest():
    assert refused("value add m 1 gg") == "Unknown unit 'gg'. Did you mean: g, kg?"


def test_a_unit_with_nothing_close_gets_no_list():
    assert refused("value add m 1 xyz") == "Unknown unit 'xyz'."


@pytest.mark.parametrize(("typed", "better"), [("1/s", "s^-1"), ("1/min", "min^-1")])
def test_one_over_a_unit_suggests_the_negative_power(typed, better):
    assert refused(f"value add k 0.1 {typed}") == (
        f"Unknown unit '{typed}'. Did you mean: {better}?"
    )


def test_one_over_a_unit_with_no_negative_power_gets_the_ordinary_suggestions():
    assert "h^-1" not in refused("value add k 0.1 1/h")


@pytest.mark.parametrize("unit", ["µg", "µL", "°C", "rpm", "bp", "kb", "U", "nM", "mm"])
def test_symbols_and_cut_units_are_refused(unit):
    assert refused(f"value add m 1 {unit}").startswith(f"Unknown unit '{unit}'.")


def test_units_match_exactly_including_case():
    assert refused("value add m 1 ML").startswith("Unknown unit 'ML'.")


def test_extra_spaces_inside_a_unit_still_match():
    assert check_unit("mol  dm^-3") == "mol  dm^-3"


def test_a_unit_is_required():
    for line in ("value add m 1", "value add m 1 +/- 0.1", "value edit m 1 # note"):
        with pytest.raises(CommandError) as raised:
            parse(line)
        assert str(raised.value).startswith("Usage: value ")


def test_a_unit_typed_with_extra_spaces_is_read_as_one_unit():
    assert parse("value add c 0.1 mol dm^-3 +/- 0.01").args["unit"] == "mol dm^-3"
    assert parse("value add c 0.1 mol   dm^-3").args["unit"] == "mol dm^-3"


def test_a_forgotten_plus_minus_still_prints_the_usage_line():
    with pytest.raises(CommandError) as raised:
        parse("value add m_crude 2.211 g 0.001")
    assert str(raised.value).startswith("Usage: value add")
