"""Suggestions for a mistyped name: the two closest, or everything of that kind.

Synthase never runs a corrected command and never asks y/n (spec D27). The rule
for "close" is in docs/decisions/0023-command-set-and-project-folder.md.
"""

from difflib import SequenceMatcher

# difflib's own default for "close enough".
CUTOFF = 0.6


def closest(typed: str, candidates: list[str]) -> list[str]:
    """The two best matches for ``typed``, or none if nothing scores CUTOFF.

    Once one candidate is close, the second best is shown too, even if it is not
    (spec: ``molarmass`` gives ``molar_mass, formula``). Equal scores keep the
    order of ``candidates``.
    """
    scores = [SequenceMatcher(None, typed, c).ratio() for c in candidates]
    if not scores or max(scores) < CUTOFF:
        return []
    ranked = sorted(range(len(candidates)), key=lambda i: -scores[i])
    return [candidates[i] for i in ranked[:2]]


def suggestion(typed: str, candidates: list[str], kind: str) -> str:
    """The end of an "Unknown …" message: the closest matches, or the full list.

    ``kind`` labels the full list, e.g. ``Fields`` gives ``Fields: name, …``.
    """
    matches = closest(typed, candidates)
    if not matches:
        return f"{kind}: {', '.join(candidates)}"
    return f"Did you mean: {', '.join(matches)}?"
