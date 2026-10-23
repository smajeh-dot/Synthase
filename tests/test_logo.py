# ruff: noqa: E501  (the pinned tables stay exactly as the handoff wrote them)
"""The start-up logo: the generator against the design's pinned tables.

LOGO_24 and LOGO_30 are the owner-approved design at 80 × 24 and 120 × 30: the
design handoff's ring, made 13 px thick at the owner's request (decision 0035).
Don't edit them to make a test pass: they are the reference.
"""

from rich.cells import cell_len

from synthase.logo import MIN_ROWS, OCTANTS, js_round, ring

# fmt: off
LOGO_24 = [
    [None, ("\U0001CEA0", "#59AAF7", None), ("\U0001CDE1", "#63B8EB", None), ("▆", "#68C3BD", None), ("▌", "#68C69A", "#65C58C"), ("▌", "#61C37E", "#6DC36C"), ("▆", "#81C252", None), ("\U0001CDDE", "#9CC247", None), ("\U0001CEA3", "#C1BA3B", None), None],
    [("\U0001CD96", "#3F8FFA", None), ("▀", "#4D9EF8", "#4090FA"), ("\U0001CD0F", "#55A7F8", None), ("\U0001CEA8", "#64BAE8", None), None, None, ("\U0001CEAB", "#97C348", None), ("\U0001CD22", "#C9B639", None), ("▀", "#DCAF32", "#ED9E2F"), ("\U0001CD48", "#EE9C2F", None)],
    [("▀", "#3F84F7", "#4882F2"), ("▀", "#3D85F8", "#4A81F0"), None, None, None, None, None, None, ("▀", "#F58931", "#F37636"), ("▀", "#F58732", "#F47836")],
    [("\U0001CD21", "#5B7BE5", None), ("▀", "#5D7AE4", "#6A74DA"), ("\U0001CDBF", "#7272D3", None), ("\U0001CEA3", "#836AC2", None), None, None, ("\U0001CEA0", "#DF505B", None), ("\U0001CDD3", "#EA5549", None), ("▀", "#F1633A", "#EE5741"), ("\U0001CD0D", "#F16539", None)],
    [None, ("\U0001CEAB", "#7570D0", None), ("\U0001CD26", "#816BC3", None), ("\U0001FB85", "#8D65B6", None), ("▌", "#9461AA", "#975FA2"), ("\U0001CDC0", "#9C5C99", "#A85B8E"), ("\U0001FB85", "#C35877", None), ("\U0001CD17", "#DE515B", None), ("\U0001CEA8", "#E8534D", None), None],
]

LOGO_30 = [
    [None, None, ("\U0001CDCB", "#61B4F4", None), ("\U0001CDE1", "#65BED6", None), ("▆", "#69C5AC", None), ("▌", "#67C696", "#64C48B"), ("▌", "#62C37F", "#6AC371"), ("▆", "#79C25A", None), ("\U0001CDDE", "#8EC34B", None), ("\U0001CDBB", "#A6C143", None), None, None],
    [("\U0001CEA0", "#4090FA", None), ("\U0001CDE5", "#4A9BF9", None), ("\U0001CD70", "#54A6F8", None), ("\U0001CD02", "#62B6F0", None), None, None, None, None, ("\U0001CD05", "#A1C245", None), ("\U0001CDAB", "#CCB638", None), ("\U0001CDE4", "#E0AB31", None), ("\U0001CEA3", "#ED9E2F", None)],
    [("▟", "#3E85F8", None), ("\U0001FB82", "#3E8EFA", "#3D85F8"), None, None, None, None, None, None, None, None, ("▀", "#F2972F", "#F58732"), ("▙", "#F58A31", None)],
    [("▜", "#4B81F0", None), ("\U0001CD17", "#4A81F1", "#587CE8"), None, None, None, None, None, None, None, None, ("▀", "#F47836", "#F26939"), ("▛", "#F37537", None)],
    [("\U0001CEAB", "#5D7AE4", None), ("\U0001CDAB", "#6776DC", None), ("\U0001CDE4", "#7072D4", None), ("\U0001CDBB", "#806CC5", None), None, None, None, None, ("\U0001CDCB", "#E15158", None), ("\U0001CDE5", "#EA5548", None), ("\U0001CD70", "#EF5A3F", None), ("\U0001CEA8", "#F1633A", None)],
    [None, None, ("\U0001CD05", "#7D6DC7", None), ("\U0001CD26", "#8868BC", None), ("\U0001FB85", "#9063B1", None), ("▌", "#9560A8", "#985EA1"), ("\U0001CDC0", "#9B5C9A", "#A25B93"), ("\U0001FB85", "#B85981", None), ("\U0001CD17", "#D35468", None), ("\U0001CD02", "#E45155", None), None, None],
]
# fmt: on


def test_the_generator_reproduces_the_design_at_80_by_24():
    assert ring(24) == LOGO_24


def test_the_generator_reproduces_the_design_at_120_by_30():
    assert ring(30) == LOGO_30


def test_the_pinned_tables_have_the_design_s_shape():
    for table, rows, filled, backgrounds in ((LOGO_24, 5, 36, 12), (LOGO_30, 6, 40, 8)):
        assert len(table) == rows
        assert all(len(row) == 2 * rows for row in table)
        cells = [cell for row in table for cell in row if cell is not None]
        assert len(cells) == filled
        assert sum(bg is not None for _, _, bg in cells) == backgrounds


def test_every_octant_and_logo_character_is_one_cell_wide():
    assert len(OCTANTS) == 256 and len(set(OCTANTS)) == 256
    used = {
        cell[0] for table in (LOGO_24, LOGO_30) for row in table for cell in row if cell
    }
    assert used <= set(OCTANTS)
    assert all(cell_len(char) == 1 for char in OCTANTS)


def test_halves_round_up_as_the_board_did():
    assert js_round(2.5) == 3
    assert js_round(24 / 5) == 5
    assert js_round(27.5 / 5) == 6


def test_every_height_the_app_draws_gives_a_square_ring():
    for height in range(MIN_ROWS, 61):
        rows = ring(height)
        assert len(rows) == js_round(height / 5)
        assert all(len(row) == 2 * len(rows) for row in rows)
