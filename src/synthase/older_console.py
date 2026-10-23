"""The older console (Windows PowerShell 5.1): ASCII in place of symbols, and
16 colours.

Synthase decides once, at start-up. The maps are the F1 design's (owner
decision D2) and change only what is drawn: stored values keep the real
symbol. The rules are in docs/decisions/0029-older-console.md.
"""

import os
import sys
from collections.abc import Mapping

from rich.segment import Segment
from textual.color import Color
from textual.content import Content, Span
from textual.filter import LineFilter

# One cell for one cell, so nothing moves: applied to every line as it is
# drawn, borders included. µ and Å each have two code points, written as
# escapes so an editor can't merge them.
CELLS = {
    "●": "o",
    "›": "-",
    "‹": "<",
    "▸": ">",
    "·": "|",
    "─": "-",
    "━": "=",
    "╭": "+",
    "╮": "+",
    "╰": "+",
    "╯": "+",
    "│": "|",
    "\u00b5": "u",
    "\u03bc": "u",
    "\u00c5": "A",
    "\u212b": "A",
}
# Longer than the symbol, so swapped in before the text is laid out.
WORDS = (
    ("°C", "degC"),
    ("°", "deg"),
    ("±", "+/-"),
    ("…", "..."),
    ("↑", "Up"),
    ("↓", "Down"),
)
TABLE = str.maketrans(CELLS)
SYMBOLS = "".join(CELLS) + "".join(symbol for symbol, _ in WORDS)
# Rich's names for a console with only 16 colours.
SIXTEEN = ("standard", "windows")


def output_encoding() -> str | None:
    """The encoding of the stream Textual draws on: stdout on Windows, else stderr."""
    stream = sys.__stdout__ if sys.platform == "win32" else sys.__stderr__
    return getattr(stream, "encoding", None)


def needs_ascii(
    encoding: str | None,
    environ: Mapping[str, str] = os.environ,
    windows: bool | None = None,
) -> bool:
    """Whether to draw ASCII in place of symbols.

    ASCII when the output can't encode the symbols, or on Windows in the old
    console window: the symbols are kept in Windows Terminal (``WT_SESSION``)
    and VS Code (``TERM_PROGRAM``), whose fonts show them.
    """
    try:
        SYMBOLS.encode(encoding or "utf-8")
    except (LookupError, UnicodeEncodeError):
        return True
    if sys.platform == "win32" if windows is None else windows:
        return not (environ.get("WT_SESSION") or environ.get("TERM_PROGRAM"))
    return False


def has_16_colours(color_system: str | None) -> bool:
    """Whether the console reports only 16 colours, as Rich names it."""
    return color_system in SIXTEEN


def words(text: str) -> str:
    """The text with each longer symbol spelt out in ASCII."""
    for symbol, plain in WORDS:
        text = text.replace(symbol, plain)
    return text


def content(text: Content) -> Content:
    """``words`` for styled text: each style keeps covering the same characters."""
    plain = text.plain
    if not any(symbol in plain for symbol, _ in WORDS):
        return text
    # Where each character of the old text starts in the new one.
    starts = []
    new = ""
    at = 0
    while at < len(plain):
        starts.append(len(new))
        for symbol, spelt in WORDS:
            if plain.startswith(symbol, at):
                new += spelt
                # A two-character symbol's second character starts inside it.
                starts.extend([len(new)] * (len(symbol) - 1))
                at += len(symbol)
                break
        else:
            new += plain[at]
            at += 1
    starts.append(len(new))
    spans = [Span(starts[s.start], starts[s.end], s.style) for s in text.spans]
    return Content(new, spans)


class Ascii(LineFilter):
    """Draws each one-cell symbol as its one-cell ASCII form."""

    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        return [
            Segment(text.translate(TABLE), style, control)
            for text, style, control in segments
        ]
