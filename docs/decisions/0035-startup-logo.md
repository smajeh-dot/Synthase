# 0035: A start-up logo beside the welcome line

## Context
On 2026-10-23 the owner designed a start-up logo in a Claude Design session: a thin ring drawn with octant characters (Unicode 16, 2 × 4 blocks per cell), coloured with the colours of Google's Antigravity 8-bit logo, which flow round the ring and drift back and forth so they seem to weave (#132). The design board and its handoff are kept outside the repo, as decision 0027's were. The owner approved it at 80 × 24 and chose every default in #132's triage on 2026-10-23. Having seen it, the owner asked the same day for a slightly thicker ring and for the welcome line beside it rather than below it.

The logo breaks three rules of the design system kept in decisions 0016 and 0027: Python never names a colour, the glyph set is closed, and there are no colour gradients. It has about 40 to 50 computed colours, uses block characters outside the glyph set, and blends colours.

## Decision
- **One exception, in one module.** `synthase/logo.py` is the only place in Synthase allowed to name colours and use octant characters. It holds the 16 colour stops and the octant table. `theme.py` and every other module keep the rules. This is a recorded exception to "Python never names a colour", the closed glyph set and "no gradients".
- **The design is pinned.** `logo.py` computes the ring with the board's own maths: a square grid of 0.5 × 0.5-unit blocks, outer radius rows − 0.125, thickness 13 px of the board's 8 px cells (1.625 units; the board's 11 px, made thicker at the owner's request), weave 15°, 1 crossing, turn 90°, colours blended in OKLab and rounded halves up. A cell holds at most two colours. Reference tables for 80 × 24 and 120 × 30 are kept in `tests/test_logo.py`, and the generator must reproduce them exactly. They are the handoff's tables remade at 13 px, otherwise unchanged.
- **Place.** The logo sits at the top of the output area, with one blank row above it and one below it, starting in the output's first column. The welcome line's two parts stack to its right, 3 cells from the ring and starting on its top row: `Synthase 0.2.0` (bold, as before), then `type 'help' for commands` (muted, as before). The rows below them stay free for more information later; none is added now. The ring itself has no text, border, bold, dim or animation.
- **Without the logo** (see Left out), the welcome line is one line, unchanged.
- **Size.** Its height is round(window rows / 5) at start-up, rounding halves up, and it is twice as many columns wide. It is drawn once and never redrawn when the window is resized, since only the bottom block redraws in place.
- **Left out** in windows under 24 rows, and whenever the older console mode is on (ASCII or 16 colours, decision 0029). Only the one-line welcome shows then.
- **Spec.** The spec's list of owner's decisions gains a short entry for the logo. `ROADMAP.md` is unchanged: the logo isn't a feature.

## Consequences
- A colour or glyph check over `src/` must skip `logo.py`.
- The octants are written out as a table, because Python 3.13's `unicodedata` is Unicode 15.1 and doesn't know them. Cascadia Mono 2404.23 and later, the font current Windows Terminal ships, has every one.
- The logo is part of the welcome, so it is trimmed with the welcome line once the output is full.
- The look depends on the terminal's font and colours, so it can only be checked on Windows, in Windows Terminal.
