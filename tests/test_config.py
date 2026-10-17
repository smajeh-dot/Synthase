"""Tests for the config template and loader.

Every value written here is invented. Real values only ever live in the owner's
workspace config, never in this repo.
"""

import textwrap

import pytest

from synthase.config import (
    WORKSPACE_CONFIG_NAME,
    ConfigError,
    load_config,
    read_template,
)


def write_config(workspace, text):
    path = workspace / WORKSPACE_CONFIG_NAME
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


INVENTED_THRESHOLD = """
    [mic.growth_threshold]
    name = "growth threshold"
    value = 0.25
    unit = "OD600"
    source = "Invented for a test"
    verified = {verified}
"""


def test_value_loads_with_its_unit(tmp_path):
    write_config(tmp_path, INVENTED_THRESHOLD.format(verified="true"))
    entry = load_config(tmp_path).get("mic.growth_threshold")
    assert entry.value == 0.25
    assert entry.unit == "OD600"
    assert entry.source == "Invented for a test"
    assert entry.verified is True


def test_verified_value_has_no_warning(tmp_path):
    write_config(tmp_path, INVENTED_THRESHOLD.format(verified="true"))
    assert load_config(tmp_path).get("mic.growth_threshold").warning == ""


def test_unverified_value_gives_warning(tmp_path):
    write_config(tmp_path, INVENTED_THRESHOLD.format(verified="false"))
    entry = load_config(tmp_path).get("mic.growth_threshold")
    assert entry.value == 0.25
    assert entry.warning == (
        "Warning: growth threshold (0.25 OD600) has not been checked against "
        "the literature yet. Treat results that use it as provisional."
    )


def test_warning_shows_ranges_and_bands(tmp_path):
    write_config(
        tmp_path,
        """
        [spectra.invented_peak]
        name = "invented peak"
        value = [1200, 1250.5]
        unit = "cm⁻¹"
        source = "Invented for a test"
        verified = false

        [fici.bands]
        name = "FICI interpretation"
        value = [
            { max = 0.3, label = "low" },
            { max = 3, label = "middle" },
            { label = "high" },
        ]
        unit = ""
        source = "Invented for a test"
        verified = false
        """,
    )
    config = load_config(tmp_path)
    assert "invented peak (1200–1250.5 cm⁻¹) has" in (
        config.get("spectra.invented_peak").warning
    )
    assert "interpretation (≤0.3 low, ≤3 middle, >3 high) has" in (
        config.get("fici.bands").warning
    )


def test_without_workspace_the_template_is_used():
    config = load_config()
    assert config.path.name == "config_template.toml"
    assert config.get("mic.growth_threshold").verified is False


def test_workspace_without_config_falls_back_to_template(tmp_path):
    config = load_config(tmp_path)
    assert config.path.name == "config_template.toml"
    assert config.keys() == load_config().keys()


def test_workspace_config_is_used_when_present(tmp_path):
    path = write_config(tmp_path, INVENTED_THRESHOLD.format(verified="true"))
    config = load_config(tmp_path)
    assert config.path == path
    assert config.get("mic.growth_threshold").value == 0.25


def test_entry_missing_from_workspace_comes_from_template(tmp_path):
    write_config(tmp_path, INVENTED_THRESHOLD.format(verified="true"))
    config = load_config(tmp_path)
    assert config.keys() == load_config().keys()
    assert config.get("dmso.limit") == load_config().get("dmso.limit")


def test_unknown_key_gives_clear_error():
    with pytest.raises(ConfigError, match=r"no entry called \[mic.nope\]"):
        load_config().get("mic.nope")


TEMPLATE_COVERS = [
    "mic.growth_threshold",
    "fici.bands",
    "dmso.limit",
    "melting_point.purity_range",
    "spectra.ir_imine_cn",
    "spectra.ir_chalcone_co",
    "spectra.nmr_imine_ch",
    "spectra.nmr_chalcone_vinyl",
    "units.mass",
    "units.volume",
    "units.concentration",
    "units.amount",
    "units.temperature",
]


def test_template_covers_every_required_constant():
    assert load_config().keys() == TEMPLATE_COVERS


def test_every_template_entry_is_an_unverified_placeholder():
    config = load_config()
    for key in config.keys():
        entry = config.get(key)
        assert entry.verified is False, key
        assert entry.source.startswith("UNVERIFIED"), key
        assert entry.warning.startswith("Warning: "), key


def test_template_text_is_readable_for_syn_init():
    assert "[mic.growth_threshold]" in read_template()


GOOD_ENTRY = """
    name = "invented"
    value = 1
    unit = ""
    source = "Invented for a test"
    verified = false
"""


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("[mic.growth_threshold\nvalue = 1\n", r", line 1"),
        ("value = 1\n", r"'value' is outside any entry"),
        ("[mic]\nvalue = 1\n", r"entry \[mic.value\]: must be a table"),
        (
            "[mic.growth_threshold]\nvalue = 1\n",
            r"entry \[mic.growth_threshold\]: missing 'name'",
        ),
        (
            "[mic.growth_threshold]" + GOOD_ENTRY + "verifed = true\n",
            r"unknown field 'verifed'",
        ),
        (
            "[mic.growth_threshold]"
            + GOOD_ENTRY.replace("verified = false", 'verified = "yes"'),
            r"'verified' must be true or false",
        ),
        (
            "[mic.growth_threshold]"
            + GOOD_ENTRY.replace('source = "Invented for a test"\n', ""),
            r"missing 'source'",
        ),
        (
            "[mic.growth_threshold]"
            + GOOD_ENTRY.replace('source = "Invented for a test"', 'source = ""'),
            r"'source' must not be empty",
        ),
        (
            "[mic.growth_threshold]" + GOOD_ENTRY.replace("value = 1", "value = true"),
            r"'value' must be",
        ),
        (
            "[spectra.peak]" + GOOD_ENTRY.replace("value = 1", "value = [9, 3]"),
            r"range must go from low to high",
        ),
        (
            "[fici.bands]"
            + GOOD_ENTRY.replace(
                "value = 1",
                'value = [{max = 4, label = "a"}, {max = 1, label = "b"},'
                ' {label = "c"}]',
            ),
            r"band limits must increase",
        ),
        (
            "[fici.bands]"
            + GOOD_ENTRY.replace(
                "value = 1", 'value = [{max = 1, label = "a"}, {max = 4, label = "b"}]'
            ),
            r"last band must have no 'max'",
        ),
    ],
)
def test_malformed_file_gives_clear_error(tmp_path, text, problem):
    path = write_config(tmp_path, text)
    with pytest.raises(ConfigError, match=problem) as error_info:
        load_config(tmp_path)
    message = str(error_info.value)
    assert message.startswith(f"Your config file has a problem: {path}")
    assert "compare it with the template" in message


def test_file_that_is_not_utf8_gives_clear_error(tmp_path):
    (tmp_path / WORKSPACE_CONFIG_NAME).write_bytes(b'unit = "\xb5L"\n')
    with pytest.raises(ConfigError, match="not saved as UTF-8 text"):
        load_config(tmp_path)
