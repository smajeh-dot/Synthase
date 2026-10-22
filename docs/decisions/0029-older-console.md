# 0029: The older console: ASCII in place of symbols, and 16 colours

## Context
Spec Section 2 says output is UTF-8 and falls back to ASCII when the console can't show a symbol, because the older console (Windows PowerShell 5.1) can mangle `±`, `µ`, `°` and `Å`. The F1 design handoff (§4, §5, §10) gives the ASCII map and a 16-colour theme, `synthase-16`, built on Windows' Campbell colours. The map was approved in #100's triage (owner decision D2, decision 0027). The full colour table and the rule for when the ASCII forms switch on weren't in the repo, so #119's triage proposed them. The owner chose those defaults on 2026-10-22.

## Decision
**When ASCII is drawn** (decided once, at start-up)
- When the output's encoding can't encode the symbols, for example `cp437`.
- On Windows, also in the old console window. Python writes UTF-8 to it, but its fonts show boxes for `✓` and the rounded corners. The symbols are kept in Windows Terminal (`WT_SESSION` is set) and VS Code (`TERM_PROGRAM` is set).

**The map** (the design's, owner decision D2)
- One cell for one cell, applied to every line as it is drawn, borders included: `✓ +`, `✗ x`, `› -`, `‹ <`, `▸ >`, `· |`, `─ -`, `━ =`, `╭ ╮ ╰ ╯ +`, `│ |`, `µ u`, `Å A`.
- Longer than the symbol, spelt out before the text is laid out, so columns don't shift: `°C degC`, `° deg`, `± +/-`, `… ...`, `↑ Up`, `↓ Down`. This covers every message, the top-rule hints, the status line and the error log. The status line's shortened folder uses `...`, and its length is counted with the three dots.
- Only the drawing changes. Stored values, the error log file and what a message says keep the real symbol.

**16 colours**
- When the console reports only 16 colours (Rich's `standard` or `windows`), the app uses the `synthase-16` theme. Each token is the nearest Campbell colour, so Rich's step down to 16 colours picks the colour meant:

| Token | Colour |
|---|---|
| background | Black `#0C0C0C` |
| text | White `#CCCCCC` |
| echo, headings | Bright White `#F2F2F2` |
| muted, status | White `#CCCCCC` |
| faint, rule, line | Bright Black `#767676` |
| accent, answer | Bright Cyan `#61D6D6` |
| success | Bright Green `#16C60C` |
| error | Bright Red `#E74856` (not DarkRed) |
| caution | Yellow `#C19C00` |

- Tokens F1 doesn't use, and the ones the table leaves out, also take Campbell colours: the selection Blue `#0037DA`, warning Bright Purple `#B4009E`, the scrollbar Black and Bright Black.
- With 16 colours, the pop-up's current row is drawn in reverse video, because bold alone may not show it.

## Consequences
- Windows 10 and 11 consoles usually report full colour, even in PowerShell 5.1, so the 16-colour theme shows mainly on older Windows or a basic terminal. Setting `$env:TEXTUAL_COLOR_SYSTEM = "standard"` before `synthase` forces it, to check the look.
- Every test draws as Windows Terminal does, whatever machine runs it. The older console's own tests switch to `cp437`, the old console window or 16 colours.
- Later output goes through the same paths (`say`, the top rule, the status line), so values with `±`, `µ` or `°` (#103, #105) are drawn in ASCII on the older console with no extra work. Typing the ASCII forms as input stays with #103.
