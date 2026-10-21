from synthase.suggest import closest, suggestion

FIELDS = ["name", "formula", "molar_mass", "density", "purity", "note"]


def test_two_closest_even_when_the_second_is_not_close():
    # Spec Section 3: formula scores below 0.6 but is still the second match.
    assert closest("molarmass", FIELDS) == ["molar_mass", "formula"]


def test_equal_scores_keep_the_list_order():
    # Plain difflib.get_close_matches would give C011 first.
    assert closest("C010", ["C001", "C011", "C123"]) == ["C001", "C011"]


def test_nothing_close_gives_no_matches():
    assert closest("boiling", FIELDS) == []


def test_one_candidate_gives_one_match():
    assert closest("C01", ["C001"]) == ["C001"]


def test_matching_is_case_sensitive():
    # An exact match is checked by the caller; a different case is only close.
    assert closest("Name", FIELDS)[0] == "name"


def test_suggestion_lists_the_closest():
    assert suggestion("molarmass", FIELDS, "Fields") == "Closest: molar_mass, formula"


def test_suggestion_lists_everything_when_nothing_is_close():
    assert suggestion("boiling", FIELDS, "Fields") == (
        "Fields: name, formula, molar_mass, density, purity, note"
    )


def test_suggestion_can_ask_did_you_mean():
    assert (
        suggestion("epx", ["compound", "exit", "exp"], "Commands", did_you_mean=True)
        == "Did you mean: exp, exit?"
    )
