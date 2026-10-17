"""Showing numbers the way every Synthase result does: to 3 significant figures."""

from decimal import ROUND_HALF_UP, Decimal


def sig_figs(value: float, figures: int = 3) -> str:
    """``value`` rounded to ``figures`` significant figures, without an exponent.

    Halves round up, as in hand-worked answers: 2.345 gives 2.35.
    """
    number = Decimal(repr(value))
    if number == 0:
        return f"{0:.{figures - 1}f}"
    rounded = _round(number, number.adjusted() - figures + 1)
    if rounded.adjusted() > number.adjusted():
        # Rounding up added a digit, e.g. 99.96 becomes 100.0: drop the last one.
        rounded = _round(number, rounded.adjusted() - figures + 1)
    return f"{rounded:f}"


def _round(number: Decimal, exponent: int) -> Decimal:
    return number.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_UP)
