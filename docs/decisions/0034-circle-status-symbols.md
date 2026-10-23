# 0034: Success and error shown as a green or red circle

## Context
Decisions 0016 and 0027 started every success message with `✓` and every error with `✗`, so that no meaning depended on colour alone. On 2026-10-23 the owner said they disliked the two symbols and asked for a plain circle in their place, green for success and red for an error, everywhere the symbols appear (#130). The owner gave a screenshot of another terminal tool as the reference for the circle's size, and asked for Synthase's own colours.

## Decision
- Success and error messages start with `●` (U+25CF) in place of `✓` and `✗`. Its colour is the message's own: `$success` green or `$error` red, bold, as the symbols were. The status line's error flag starts with the same red `●`.
- The size is the reference screenshot's. Measured there, the circle is 11 px across in a 13 px cell, the height of a lowercase `a`, which is `●` drawn one cell wide in the terminal's own font. The smaller bullet `•` measured 7 px, so it was not used.
- On the older console (decision 0029) `●` is drawn as `o`, still in green or red. The old console's raster font and `cp437` have no `●`.
- The other symbols (`>`, `i`, `›`, `‹`) are unchanged.

## Consequences
- Success and error are now told apart by colour and by the message's words, not by their symbol. This replaces the part of decisions 0016 and 0027 that gave every message kind its own symbol so no meaning depended on colour alone, for success and error only. Someone who can't tell red from green sees the same circle for both.
- In decision 0029's ASCII map, `✓ +` and `✗ x` are replaced by `● o`.
- Decision 0019's colour rule ("as an error (`✗`) already is") now reads with the red `●`.
- The circle's size depends on the terminal's font, so it can only be checked on Windows: in Windows Terminal with its default font, Cascadia Mono.
