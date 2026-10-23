# 0035: A start-up logo above the welcome line

## Context
On 2026-10-23 the owner designed a start-up logo in a Claude Design session: a thin ring drawn with octant characters (Unicode 16, 2 × 4 blocks per cell), coloured with the colours of Google's Antigravity 8-bit logo, which flow round the ring and drift back and forth so they seem to weave (#132). The design board and its handoff are kept outside the repo, as decision 0027's were. The owner approved it at 80 × 24 and chose every default in #132's triage on 2026-10-23.

The logo breaks three rules of the design system kept in decisions 0016 and 0027: Python never names a colour, the glyph set is closed, and there are no colour gradients. It has 31 to 40 computed colours, uses block characters outside the glyph set, and blends colours.

## Decision
- **One exception, in one module.** `synthase/logo.py` is the only place in Synthase allowed to name colours and use octant characters. It holds the 16 colour stops and the octant table. `theme.py` and every other module keep the rules. This is a recorded exception to "Python never names a colour", the closed glyph set and "no gradients".
- **The design is pinned.** `logo.py` computes the ring with the board's own maths: a square grid of 0.5 × 0.5-unit blocks, outer radius rows − 0.125, thickness 1.375 units, weave 15°, 1 crossing, turn 90°, colours blended in OKLab and rounded halves up. A cell holds at most two colours. The handoff's two reference tables, for 80 × 24 and 120 × 30, are kept in `tests/test_logo.py`, and the generator must reproduce them exactly.
- **Place.** The logo sits at the top of the output area, with one blank row above it and one between it and the welcome line, starting in the welcome line's column. It has no text, border, bold, dim or animation; the welcome line is unchanged.
- **Size.** Its height is round(window rows / 5) at start-up, rounding halves up, and it is twice as many columns wide. It is drawn once and never redrawn when the window is resized, since only the bottom block redraws in place.
- **Left out** in windows under 24 rows, and whenever the older console mode is on (ASCII or 16 colours, decision 0029). Only the welcome line shows then.
- **Spec.** The spec's list of owner's decisions gains a short entry for the logo. `ROADMAP.md` is unchanged: the logo isn't a feature.

## Consequences
- A colour or glyph check over `src/` must skip `logo.py`.
- The octants are written out as a table, because Python 3.13's `unicodedata` is Unicode 15.1 and doesn't know them. Cascadia Mono 2404.23 and later, the font current Windows Terminal ships, has every one.
- The logo counts as one widget of the output area, so it is trimmed with the oldest messages once the output is full.
- The look depends on the terminal's font and colours, so it can only be checked on Windows, in Windows Terminal.
