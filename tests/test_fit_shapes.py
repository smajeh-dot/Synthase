"""The shapes table that fit check uses for its settings counts."""

from synthase.fit_shapes import MOST_SETTINGS, SHAPES


def test_each_shape_has_its_number_of_settings():
    assert SHAPES == {
        "line": 2,
        "exponential": 3,
        "s-curve": 4,
        "growth": 4,
        "michaelis-menten": 2,
        "arrhenius": 2,
    }


def test_with_no_shape_the_checks_use_the_most_settings():
    # Worked by hand: s-curve and growth both have 4, more than any other.
    assert MOST_SETTINGS == 4
