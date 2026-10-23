"""The older console: ASCII in place of symbols, and 16 colours (decision 0029).

Every value is invented.
"""

from rich.segment import Segment
from textual.color import Color
from textual.content import Content, Span

from synthase.older_console import Ascii, content, has_16_colours, needs_ascii, words

WINDOWS_TERMINAL = {"WT_SESSION": "invented"}
VS_CODE = {"TERM_PROGRAM": "vscode"}


def test_an_encoding_without_the_symbols_needs_ascii():
    assert needs_ascii("cp437", WINDOWS_TERMINAL, windows=True)
    assert needs_ascii("cp1252", {}, windows=False)
    assert needs_ascii("ascii", {}, windows=False)
    assert needs_ascii("no-such-encoding", {}, windows=False)


def test_utf_8_keeps_the_symbols_except_in_the_old_console_window():
    assert not needs_ascii("utf-8", {}, windows=False)
    assert not needs_ascii("utf-8", WINDOWS_TERMINAL, windows=True)
    assert not needs_ascii("utf-8", VS_CODE, windows=True)
    assert needs_ascii("utf-8", {}, windows=True)


def test_16_colours_is_rich_standard_or_windows():
    assert has_16_colours("standard")
    assert has_16_colours("windows")
    assert not has_16_colours("256")
    assert not has_16_colours("truecolor")
    assert not has_16_colours(None)


def test_one_cell_symbols_are_drawn_as_one_cell():
    line = [Segment("● Done · 5 µL "), Segment("╭─━│╯ › ‹ ▸ ● 1 Å")]
    drawn = Ascii().apply(line, Color(0, 0, 0))
    assert [s.text for s in drawn] == ["o Done | 5 uL ", "+-=|+ - < > o 1 A"]
    # The other code points for micro and angstrom.
    assert Ascii().apply([Segment("μÅ")], Color(0, 0, 0))[0].text == "uA"


def test_longer_symbols_are_spelt_out():
    assert words("2.003 g ± 0.001") == "2.003 g +/- 0.001"
    assert words("25 °C, 90°") == "25 degC, 90deg"
    assert words("~\\…\\aspirin") == "~\\...\\aspirin"
    assert words("↑ older · ↓ newer") == "Up older · Down newer"


def test_styles_keep_their_characters_when_spelt_out():
    text = Content("± 0.001 g at 25 °C", [Span(0, 1, "bold"), Span(13, 18, "italic")])
    drawn = content(text)
    assert drawn.plain == "+/- 0.001 g at 25 degC"
    assert [(drawn.plain[s.start : s.end], s.style) for s in drawn.spans] == [
        ("+/-", "bold"),
        ("25 degC", "italic"),
    ]
    plain = Content("no symbols")
    assert content(plain) is plain
